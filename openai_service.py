import os
import logging
from typing import List, Dict, Optional

from openai import OpenAI


logger = logging.getLogger(__name__)


def _get_openai_client(api_key: Optional[str] = None) -> OpenAI:
    """환경 변수 또는 인자로부터 OpenAI 클라이언트를 생성한다."""
    effective_api_key = api_key or os.environ.get("OPENAI_API_KEY")
    if not effective_api_key:
        raise ValueError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=effective_api_key)


def generate_review_content(
    messages: List[Dict],
    model: str,
    temperature: float,
    api_key: Optional[str] = None,
) -> str:
    """주어진 messages를 기반으로 OpenAI ChatCompletion 결과 텍스트를 반환한다."""

    client = _get_openai_client(api_key=api_key)

    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=messages,
    )

    return response.choices[0].message.content.strip()
