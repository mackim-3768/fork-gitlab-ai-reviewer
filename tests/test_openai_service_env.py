import os

import pytest

from openai_service import generate_review_content


@pytest.mark.integration
def test_generate_review_content_with_real_openai():
    """실제 OpenAI API를 호출하는 통합 테스트.

    OPENAI_API_KEY 가 설정되지 않은 환경에서는 테스트를 건너뛴다.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY is not set; skipping integration test.")

    model = os.getenv("OPENAI_API_MODEL") or "gpt-3.5-turbo"

    messages = [
        {
            "role": "user",
            "content": "간단한 테스트용 코드 리뷰 코멘트를 생성해 주세요.",
        }
    ]

    result = generate_review_content(
        messages=messages,
        model=model,
        temperature=1.0,
        api_key=api_key,
    )

    assert isinstance(result, str)
    assert result.strip()
