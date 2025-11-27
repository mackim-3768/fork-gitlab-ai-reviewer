import os
import logging

from flask import Flask, request

from .gitlab_client import (
    post_merge_request_comment,
    post_commit_comment,
)
from .task_queue import (
    initialize_review_queue,
    enqueue_merge_request_review,
    enqueue_push_review,
)


app = Flask(__name__)
gitlab_access_token = os.environ.get("GITLAB_ACCESS_TOKEN")
gitlab_base_url = os.environ.get("GITLAB_URL")
gitlab_api_base_url = (
    f"{gitlab_base_url.rstrip('/')}/api/v4" if gitlab_base_url else None
)


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _get_int_env(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default

    try:
        parsed = int(value)
        if parsed <= 0:
            raise ValueError
        return parsed
    except ValueError:
        logger = logging.getLogger(__name__)
        logger.warning("Invalid %s '%s', using default %s", name, value, default)
        return default


log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_name, logging.INFO)
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

if log_level == logging.INFO and log_level_name != "INFO":
    logger.warning(
        "Invalid LOG_LEVEL '%s', defaulting to INFO",
        log_level_name,
    )

enable_merge_request_review = _get_bool_env("ENABLE_MERGE_REQUEST_REVIEW", True)
enable_push_review = _get_bool_env("ENABLE_PUSH_REVIEW", True)

openai_model = os.environ.get("OPENAI_API_MODEL") or "gpt-5-mini"

review_max_requests_per_minute = _get_int_env(
    "REVIEW_MAX_REQUESTS_PER_MINUTE",
    2,
)
review_worker_concurrency = _get_int_env("REVIEW_WORKER_CONCURRENCY", 1)
review_max_pending_jobs_soft_limit = _get_int_env("REVIEW_MAX_PENDING_JOBS", 100)

initialize_review_queue(
    max_requests_per_minute=review_max_requests_per_minute,
    worker_concurrency=review_worker_concurrency,
    max_pending_jobs_soft_limit=review_max_pending_jobs_soft_limit,
)

AI_PROGRESS_MESSAGE = (
    "AI가 코드를 검토 중입니다. 잠시만 기다려 주세요.\n"
    "\n"
    "이 코멘트는 자동으로 생성되었습니다."
)


def handle_merge_request_event(payload):
    action = payload["object_attributes"]["action"]
    if action != "open":
        return "Not a  PR open", 200

    project_id = payload["project"]["id"]
    mr_id = payload["object_attributes"]["iid"]
    logger.info(
        "Handling merge_request: project_id=%s, mr_id=%s, action=%s",
        project_id,
        mr_id,
        action,
    )

    # 진행중 안내 코멘트
    try:
        post_merge_request_comment(
            gitlab_api_base_url,
            gitlab_access_token,
            project_id,
            mr_id,
            AI_PROGRESS_MESSAGE,
        )
    except Exception:
        logger.exception(
            "Failed to post AI progress comment for merge_request: project_id=%s, mr_id=%s",
            project_id,
            mr_id,
        )

    try:
        enqueue_merge_request_review(
            project_id=project_id,
            merge_request_iid=mr_id,
            gitlab_api_base_url=gitlab_api_base_url,
            gitlab_access_token=gitlab_access_token,
            openai_model=openai_model,
        )
    except Exception:
        logger.exception(
            "Failed to enqueue merge_request review task: project_id=%s, mr_id=%s",
            project_id,
            mr_id,
        )

    return "OK", 200


def handle_push_event(payload):
    project_id = payload["project_id"]
    commit_id = payload["after"]
    logger.info(
        "Handling push event: project_id=%s, commit_id=%s",
        project_id,
        commit_id,
    )

    # 진행중 안내 코멘트
    try:
        post_commit_comment(
            gitlab_api_base_url,
            gitlab_access_token,
            project_id,
            commit_id,
            AI_PROGRESS_MESSAGE,
        )
    except Exception:
        logger.exception(
            "Failed to post AI progress comment for commit: project_id=%s, commit_id=%s",
            project_id,
            commit_id,
        )

    try:
        enqueue_push_review(
            project_id=project_id,
            commit_id=commit_id,
            gitlab_api_base_url=gitlab_api_base_url,
            gitlab_access_token=gitlab_access_token,
            openai_model=openai_model,
        )
    except Exception:
        logger.exception(
            "Failed to enqueue push review task: project_id=%s, commit_id=%s",
            project_id,
            commit_id,
        )

    return "OK", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    webhook_secret_token = os.environ.get("GITLAB_WEBHOOK_SECRET_TOKEN")
    received_token = request.headers.get("X-Gitlab-Token")
    if received_token != webhook_secret_token:
        logger.warning("Unauthorized webhook request: invalid X-Gitlab-Token")
        return "Unauthorized", 403

    payload = request.json
    object_kind = payload.get("object_kind")
    logger.info("Received webhook: object_kind=%s", object_kind)

    if object_kind == "merge_request":
        if not enable_merge_request_review:
            logger.info(
                "merge_request handling disabled by ENABLE_MERGE_REQUEST_REVIEW",
            )
            return "merge_request handling disabled", 200
        return handle_merge_request_event(payload)

    if object_kind == "push":
        if not enable_push_review:
            logger.info(
                "push handling disabled by ENABLE_PUSH_REVIEW",
            )
            return "push handling disabled", 200
        return handle_push_event(payload)

    logger.info("Ignoring unsupported object_kind: %s", object_kind)

    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9655)
