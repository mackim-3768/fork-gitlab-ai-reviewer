import logging
import queue
import threading
from typing import Optional, Union

from .rate_limiter import FixedIntervalRateLimiter
from .review_service import (
    MergeRequestReviewTask,
    PushReviewTask,
    run_merge_request_review,
    run_push_review,
)


logger = logging.getLogger(__name__)

ReviewTask = Union[MergeRequestReviewTask, PushReviewTask]


_job_queue: "queue.Queue[ReviewTask]" = queue.Queue()
_rate_limiter: Optional[FixedIntervalRateLimiter] = None
_max_pending_jobs_soft_limit: Optional[int] = None
_workers_started = False


def initialize_review_queue(
    max_requests_per_minute: int,
    worker_concurrency: int,
    max_pending_jobs_soft_limit: Optional[int] = None,
) -> None:
    """리뷰 작업 큐와 워커 스레드를 초기화한다.

    여러 번 호출되어도 최초 한 번만 워커를 생성하도록 설계한다.
    """

    global _rate_limiter, _max_pending_jobs_soft_limit, _workers_started

    if _workers_started:
        return

    if worker_concurrency <= 0:
        raise ValueError("worker_concurrency must be positive")

    _rate_limiter = FixedIntervalRateLimiter(max_requests_per_minute)
    _max_pending_jobs_soft_limit = max_pending_jobs_soft_limit

    for index in range(worker_concurrency):
        worker = threading.Thread(
            target=_worker_loop,
            name=f"review-worker-{index + 1}",
            daemon=True,
        )
        worker.start()

    _workers_started = True
    logger.info(
        "Initialized review queue: workers=%s, max_requests_per_minute=%s, max_pending_jobs_soft_limit=%s",
        worker_concurrency,
        max_requests_per_minute,
        max_pending_jobs_soft_limit,
    )


def enqueue_merge_request_review(
    project_id: int,
    merge_request_iid: int,
    gitlab_api_base_url: str,
    gitlab_access_token: str,
    openai_model: str,
) -> None:
    """머지 요청 리뷰 작업을 큐에 추가한다."""

    task = MergeRequestReviewTask(
        project_id=project_id,
        merge_request_iid=merge_request_iid,
        gitlab_api_base_url=gitlab_api_base_url,
        gitlab_access_token=gitlab_access_token,
        openai_model=openai_model,
    )
    _job_queue.put(task)
    _log_if_queue_too_long()


def enqueue_push_review(
    project_id: int,
    commit_id: str,
    gitlab_api_base_url: str,
    gitlab_access_token: str,
    openai_model: str,
) -> None:
    """푸시(커밋) 리뷰 작업을 큐에 추가한다."""

    task = PushReviewTask(
        project_id=project_id,
        commit_id=commit_id,
        gitlab_api_base_url=gitlab_api_base_url,
        gitlab_access_token=gitlab_access_token,
        openai_model=openai_model,
    )
    _job_queue.put(task)
    _log_if_queue_too_long()


def _log_if_queue_too_long() -> None:
    if not _max_pending_jobs_soft_limit or _max_pending_jobs_soft_limit <= 0:
        return

    size = _job_queue.qsize()
    if size > _max_pending_jobs_soft_limit:
        logger.warning(
            "Review task queue length %s exceeded soft limit %s",
            size,
            _max_pending_jobs_soft_limit,
        )


def _worker_loop() -> None:
    assert (
        _rate_limiter is not None
    ), "Rate limiter must be initialized before starting workers."

    while True:
        task = _job_queue.get()
        try:
            _rate_limiter.acquire()

            if isinstance(task, MergeRequestReviewTask):
                run_merge_request_review(task)
            elif isinstance(task, PushReviewTask):
                run_push_review(task)
            else:
                logger.error("Unknown task type: %r", task)
        except Exception:  # noqa: BLE001 - 워커는 항상 살아 있어야 한다.
            logger.exception("Unexpected error while processing review task")
        finally:
            _job_queue.task_done()
