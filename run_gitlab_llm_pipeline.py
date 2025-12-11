"""GitLab MR diff를 가져와 LLM 리뷰 파이프라인을 직접 실행하는 스크립트.

프로젝트 루트의 .env(또는 환경 변수)에서 다음 값을 읽어 사용한다.
- GITLAB_URL
- GITLAB_ACCESS_TOKEN
- GITLAB_TEST_PROJECT_ID
- GITLAB_TEST_MERGE_REQUEST_IID
- LLM_PROVIDER, LLM_MODEL 및 provider별 필수 API 키

사용 예:

    uv run python run_gitlab_llm_pipeline.py

또는 가상환경이 활성화된 상태에서:

    python run_gitlab_llm_pipeline.py
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from src.gitlab_client import get_merge_request_changes
from src.review_chain import get_review_chain
from src.types import GitDiffChange, MergeRequestChangesResponse, LLMReviewResult


PROJECT_ROOT = Path(__file__).resolve().parent
ENV_PATH = PROJECT_ROOT / ".env"

if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=False)


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        msg = f"{name} is not set; unable to run GitLab→LLM pipeline."
        raise RuntimeError(msg)
    return value


def _setup_logging() -> logging.Logger:
    log_level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)
    logging.basicConfig(level=log_level)
    logger = logging.getLogger("gitlab_llm_pipeline")

    if log_level == logging.INFO and log_level_name != "INFO":
        logger.warning("Invalid LOG_LEVEL '%s', defaulting to INFO", log_level_name)

    return logger


def main() -> None:
    """GitLab MR diff를 기반으로 LLM 리뷰를 생성하고 콘솔에 출력한다."""

    logger = _setup_logging()

    base_url = _require_env("GITLAB_URL")
    access_token = _require_env("GITLAB_ACCESS_TOKEN")
    project_id_raw = _require_env("GITLAB_TEST_PROJECT_ID")
    mr_iid_raw = _require_env("GITLAB_TEST_MERGE_REQUEST_IID")

    try:
        project_id = int(project_id_raw)
        merge_request_iid = int(mr_iid_raw)
    except ValueError as exc:  # noqa: TRY003 - 환경 변수 검증용 단순 래핑
        raise ValueError(
            "GITLAB_TEST_PROJECT_ID and GITLAB_TEST_MERGE_REQUEST_IID must be integers",
        ) from exc

    api_base_url = f"{base_url.rstrip('/')}/api/v4"

    logger.info(
        "Fetching merge_request changes: base_url=%s, project_id=%s, mr_iid=%s",
        api_base_url,
        project_id,
        merge_request_iid,
    )

    mr_changes: MergeRequestChangesResponse = get_merge_request_changes(
        api_base_url=api_base_url,
        access_token=access_token,
        project_id=project_id,
        merge_request_iid=merge_request_iid,
    )

    changes: list[GitDiffChange] = mr_changes.get("changes", [])
    if not changes:
        logger.warning("No changes found in target merge request; nothing to review.")
        return

    logger.info("Running review_chain with %s changes", len(changes))

    review_chain = get_review_chain()
    result: LLMReviewResult = review_chain.invoke(changes)

    content = (result.get("content") or "").strip()

    print("\n===== LLM REVIEW START =====\n")
    if content:
        print(content)
    else:
        print("[warning] LLM returned empty content")
    print("\n===== LLM REVIEW END =====\n")

    print("[LLM metadata]")
    provider = result.get("provider")
    model = result.get("model")
    elapsed = result.get("elapsed_seconds")
    if provider is not None:
        print(f"provider={provider}")
    if model is not None:
        print(f"model={model}")
    if elapsed is not None:
        print(f"elapsed_seconds={elapsed}")

    for key in ("input_tokens", "output_tokens", "total_tokens"):
        value = result.get(key)
        if value is not None:
            print(f"{key}={value}")


if __name__ == "__main__":
    main()
