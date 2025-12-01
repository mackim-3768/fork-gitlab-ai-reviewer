import os

import pytest

from src.gitlab_client import get_merge_request_changes
from src.review_prompt import generate_review_prompt


def _require_env(name: str) -> str:
    """통합 테스트 실행에 필요한 환경 변수가 없으면 테스트를 건너뛴다."""
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is not set; skipping GitLab integration tests.")
    return value


@pytest.mark.integration
def test_generate_review_prompt_with_real_gitlab():
    # TODO: gitlab 로직과 단위테스트를 분리해야 함

    """실제 GitLab API에서 MR 변경사항을 조회하는 통합 테스트.

    다음 환경변수가 설정된 경우에만 실행된다.
    - GITLAB_URL
    - GITLAB_ACCESS_TOKEN
    - GITLAB_TEST_PROJECT_ID
    - GITLAB_TEST_MERGE_REQUEST_IID
    """
    base_url = _require_env("GITLAB_URL")
    access_token = _require_env("GITLAB_ACCESS_TOKEN")
    project_id = int(_require_env("GITLAB_TEST_PROJECT_ID"))
    merge_request_iid = int(_require_env("GITLAB_TEST_MERGE_REQUEST_IID"))

    api_base_url = f"{base_url.rstrip('/')}/api/v4"

    data = get_merge_request_changes(
        api_base_url=api_base_url,
        access_token=access_token,
        project_id=project_id,
        merge_request_iid=merge_request_iid,
    )

    changes = data.get("changes", [])

    messages = generate_review_prompt(changes)

    print(messages)

    assert isinstance(messages, list)
    assert len(messages) > 0
