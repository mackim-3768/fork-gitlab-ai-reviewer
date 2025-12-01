import logging
import os
from enum import Enum
from time import perf_counter
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.messages import BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

from .types import ChatMessageDict, LLMReviewResult


logger = logging.getLogger(__name__)


class LLMProvider(str, Enum):
    OPENAI = "openai"
    GEMINI = "gemini"
    OLLAMA = "ollama"


def _get_llm_provider() -> LLMProvider:
    raw = os.environ.get("LLM_PROVIDER", "openai").strip().lower()
    try:
        return LLMProvider(raw)
    except ValueError as exc:  # noqa: TRY003 - 환경 변수 검증을 위한 단순 예외 래핑
        raise ValueError(f"Unsupported LLM_PROVIDER: {raw}") from exc


def _get_llm_model() -> str:
    value = os.environ.get("LLM_MODEL")
    if not value or not value.strip():
        return "gpt-5-mini"
    return value.strip()


def _get_llm_timeout_seconds() -> float:
    raw_value = os.environ.get("LLM_TIMEOUT_SECONDS")
    if not raw_value:
        return 300.0

    try:
        seconds = float(raw_value)
        if seconds <= 0:
            raise ValueError
        return seconds
    except ValueError:
        logger.warning(
            "Invalid LLM timeout '%s', using default 300s",
            raw_value,
        )
        return 300.0


def _to_langchain_messages(messages: List[ChatMessageDict]) -> List[BaseMessage]:
    lc_messages: List[BaseMessage] = []
    for message in messages:
        role = message.get("role")
        content = message.get("content", "")

        if role == "system":
            lc_messages.append(SystemMessage(content=content))
        elif role == "user":
            lc_messages.append(HumanMessage(content=content))
        elif role == "assistant":
            lc_messages.append(AIMessage(content=content))
        else:
            logger.warning("Unknown message role '%s', treating as user", role)
            lc_messages.append(HumanMessage(content=content))

    return lc_messages


def _create_openai_llm(model: str, temperature: float) -> ChatOpenAI:
    timeout = _get_llm_timeout_seconds()
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set")

    # gpt-5 계열 temperature 제약을 최대한 보존
    if model.startswith("gpt-5") and temperature != 1:
        logger.info(
            "Model %s only supports default temperature; ignoring explicit temperature=%s",
            model,
            temperature,
        )
        temperature = 1.0

    return ChatOpenAI(
        model=model,
        api_key=api_key,
        temperature=temperature,
        timeout=timeout,
    )


def _create_gemini_llm(model: str, temperature: float) -> ChatGoogleGenerativeAI:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GOOGLE_API_KEY is not set (required when LLM_PROVIDER=gemini)",
        )

    timeout = _get_llm_timeout_seconds()
    return ChatGoogleGenerativeAI(
        model=model,
        api_key=api_key,
        temperature=temperature,
        # langchain-google-genai 에서는 timeout을 client 옵션으로 처리하므로,
        # 여기서는 모델 수준에서만 전달한다.
    )


def _create_ollama_llm(model: str, temperature: float) -> ChatOllama:
    base_url = os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434"
    timeout = _get_llm_timeout_seconds()

    return ChatOllama(
        model=model,
        temperature=temperature,
        base_url=base_url,
        request_timeout=timeout,
    )


def _create_llm(model: str, temperature: float) -> BaseChatModel:
    """환경 변수 기반 provider 설정에 따라 적절한 LangChain Chat 모델을 생성한다."""

    provider = _get_llm_provider()
    logger.info("Creating LLM: provider=%s, model=%s", provider.value, model)

    if provider is LLMProvider.OPENAI:
        return _create_openai_llm(model=model, temperature=temperature)
    if provider is LLMProvider.GEMINI:
        return _create_gemini_llm(model=model, temperature=temperature)
    if provider is LLMProvider.OLLAMA:
        return _create_ollama_llm(model=model, temperature=temperature)

    raise ValueError(f"Unsupported LLM provider: {provider}")


def generate_review_content_with_stats(
    messages: List[ChatMessageDict],
) -> LLMReviewResult:
    """주어진 messages를 기반으로 LLM을 호출하고, 결과와 메타데이터를 함께 반환한다."""

    lc_messages = _to_langchain_messages(messages)

    # temperature는 리뷰 결과의 일관성을 위해 1.0으로 고정한다.
    model = _get_llm_model()
    provider = _get_llm_provider()
    llm = _create_llm(model=model, temperature=1.0)

    started_at = perf_counter()
    response = llm.invoke(lc_messages)
    elapsed = perf_counter() - started_at

    content = response.content.strip()

    result: LLMReviewResult = {
        "content": content,
        "provider": provider.value,
        "model": model,
        "elapsed_seconds": elapsed,
    }

    # 토큰 사용량은 provider/라이브러리마다 제공 여부가 다르므로, 존재하는 경우에만 추출한다.
    input_tokens = None
    output_tokens = None
    total_tokens = None

    usage_metadata = getattr(response, "usage_metadata", None)
    if isinstance(usage_metadata, dict):
        input_tokens = usage_metadata.get("input_tokens")
        output_tokens = usage_metadata.get("output_tokens")
        total_tokens = usage_metadata.get("total_tokens")
    else:
        response_metadata = getattr(response, "response_metadata", None)
        if isinstance(response_metadata, dict):
            token_usage = response_metadata.get("token_usage") or response_metadata.get(
                "usage"
            )
            if isinstance(token_usage, dict):
                input_tokens = token_usage.get("prompt_tokens") or token_usage.get(
                    "input_tokens"
                )
                output_tokens = token_usage.get("completion_tokens") or token_usage.get(
                    "output_tokens"
                )
                total_tokens = token_usage.get("total_tokens")

    if input_tokens is not None:
        result["input_tokens"] = int(input_tokens)
    if output_tokens is not None:
        result["output_tokens"] = int(output_tokens)
    if total_tokens is not None:
        result["total_tokens"] = int(total_tokens)

    return result


def generate_review_content(
    messages: List[ChatMessageDict],
) -> str:
    """기존 API를 유지하기 위한 래퍼. 리뷰 텍스트 문자열만 반환한다."""

    result = generate_review_content_with_stats(messages)
    return result["content"]


def get_llm_provider_name() -> str:
    try:
        provider = _get_llm_provider()
        return provider.value
    except ValueError as exc:
        logger.error("Failed to resolve LLM provider: %s", exc)
        return "unknown"


def get_llm_model_name() -> str:
    return _get_llm_model()
