import logging
import queue
import threading
from typing import Optional

from .boy_scout_service import BoyScoutReviewTask, run_boy_scout_review
from .rate_limiter import FixedIntervalRateLimiter


logger = logging.getLogger(__name__)

_job_queue: "queue.Queue[BoyScoutReviewTask]" = queue.Queue()
_rate_limiter: Optional[FixedIntervalRateLimiter] = None
_max_pending_jobs_soft_limit: Optional[int] = None
_workers_started = False


def initialize_boy_scout_queue(
    max_requests_per_minute: int,
    worker_concurrency: int,
    max_pending_jobs_soft_limit: Optional[int] = None,
) -> None:
    """보이스카웃 리뷰 전용 큐와 워커를 초기화한다."""

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
            name=f"boy-scout-worker-{index + 1}",
            daemon=True,
        )
        worker.start()

    _workers_started = True
    logger.info(
        "Initialized boy scout queue: workers=%s, max_requests_per_minute=%s, max_pending_jobs_soft_limit=%s",
        worker_concurrency,
        max_requests_per_minute,
        max_pending_jobs_soft_limit,
    )


def enqueue_boy_scout_review(
    *,
    project_id: int,
    merge_request_iid: int,
    source_ref: str,
    gitlab_api_base_url: str,
    gitlab_access_token: str,
    max_files: int,
    max_file_chars: int,
    max_total_chars: int,
) -> None:
    """보이스카웃 리뷰 작업을 큐에 추가한다."""

    task = BoyScoutReviewTask(
        project_id=project_id,
        merge_request_iid=merge_request_iid,
        source_ref=source_ref,
        gitlab_api_base_url=gitlab_api_base_url,
        gitlab_access_token=gitlab_access_token,
        max_files=max_files,
        max_file_chars=max_file_chars,
        max_total_chars=max_total_chars,
    )
    _job_queue.put(task)
    _log_if_queue_too_long()


def _log_if_queue_too_long() -> None:
    if not _max_pending_jobs_soft_limit or _max_pending_jobs_soft_limit <= 0:
        return

    size = _job_queue.qsize()
    if size > _max_pending_jobs_soft_limit:
        logger.warning(
            "Boy scout task queue length %s exceeded soft limit %s",
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
            run_boy_scout_review(task)
        except Exception:  # noqa: BLE001 - 워커는 항상 살아 있어야 한다.
            logger.exception("Unexpected error while processing boy scout review task")
        finally:
            _job_queue.task_done()
