from __future__ import annotations

import logging

from flask import Flask

from src.app.config import AppSettings
from src.app.orchestrator import WebhookOrchestrator
from src.app.webhook import register_webhook_routes
from src.domains.boy_scout.service import BoyScoutReviewService
from src.domains.review.service import ReviewService
from src.domains.review.tasks import MergeRequestReviewTask, PushReviewTask
from src.domains.boy_scout.tasks import BoyScoutReviewTask
from src.infra.clients.gitlab import GitLabClient, GitLabClientConfig
from src.infra.clients.llm import LLMClient, LLMClientConfig
from src.infra.monitoring.llm_webhook import LLMMonitoringWebhookClient
from src.infra.queue.inprocess_queue import InProcessWorkerQueue
from src.infra.repositories.boy_scout_state_repo import BoyScoutStateRepository
from src.infra.repositories.review_cache_repo import ReviewCacheRepository


def _setup_logging(log_level_name: str) -> None:
    level = getattr(logging, log_level_name.upper(), None)
    if not isinstance(level, int):
        level = logging.INFO
        logging.basicConfig(level=level)
        logging.getLogger(__name__).warning(
            "Invalid LOG_LEVEL '%s', defaulting to INFO",
            log_level_name,
        )
        return

    logging.basicConfig(level=level)


def create_app() -> Flask:
    settings = AppSettings.from_env()
    _setup_logging(settings.log_level)

    gitlab_client = GitLabClient(
        GitLabClientConfig(
            api_base_url=settings.gitlab_api_base_url,
            access_token=settings.gitlab_access_token,
            timeout_seconds=settings.gitlab_request_timeout_seconds,
        )
    )

    llm_client = LLMClient(
        LLMClientConfig(
            provider=settings.llm_provider,
            model=settings.llm_model,
            timeout_seconds=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
            openai_api_key=settings.openai_api_key,
            google_api_key=settings.google_api_key,
            ollama_base_url=settings.ollama_base_url,
            openrouter_api_key=settings.openrouter_api_key,
            openrouter_base_url=settings.openrouter_base_url,
        )
    )

    monitoring_client = LLMMonitoringWebhookClient(
        webhook_url=settings.llm_monitoring_webhook_url,
        timeout_seconds=settings.llm_monitoring_timeout_seconds,
    )
    review_cache_repo = ReviewCacheRepository(settings.review_cache_db_path)
    boy_scout_state_repo = BoyScoutStateRepository(settings.boy_scout_state_db_path)

    review_service = ReviewService(
        gitlab_client=gitlab_client,
        llm_client=llm_client,
        review_cache_repo=review_cache_repo,
        monitoring_client=monitoring_client,
        review_system_prompt=settings.review_system_prompt,
    )
    boy_scout_service = BoyScoutReviewService(
        gitlab_client=gitlab_client,
        llm_client=llm_client,
        state_repo=boy_scout_state_repo,
        monitoring_client=monitoring_client,
    )

    review_queue: InProcessWorkerQueue[MergeRequestReviewTask | PushReviewTask] | None = None
    if settings.enable_merge_request_review or settings.enable_push_review:
        review_queue = InProcessWorkerQueue(
            name="review",
            handler=review_service.run_task,
            max_requests_per_minute=settings.review_max_requests_per_minute,
            worker_concurrency=settings.review_worker_concurrency,
            max_pending_jobs_soft_limit=settings.review_max_pending_jobs,
        )

    boy_scout_queue: InProcessWorkerQueue[BoyScoutReviewTask] | None = None
    if settings.enable_boy_scout_review:
        boy_scout_queue = InProcessWorkerQueue(
            name="boy-scout",
            handler=boy_scout_service.run_task,
            max_requests_per_minute=settings.boy_scout_max_requests_per_minute,
            worker_concurrency=settings.boy_scout_worker_concurrency,
            max_pending_jobs_soft_limit=settings.boy_scout_max_pending_jobs,
        )

    orchestrator = WebhookOrchestrator(
        settings=settings,
        gitlab_client=gitlab_client,
        review_queue=review_queue,
        boy_scout_queue=boy_scout_queue,
        boy_scout_state_repo=boy_scout_state_repo,
    )

    app = Flask(__name__)
    register_webhook_routes(app, settings=settings, orchestrator=orchestrator)
    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9655)
