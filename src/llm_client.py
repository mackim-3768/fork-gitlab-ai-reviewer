import logging
import os
from enum import Enum
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.messages import BaseMessage
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_ollama import ChatOllama

from .types import ChatMessageDict


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


def generate_review_content(
    messages: List[ChatMessageDict],
) -> str:
    """주어진 messages를 기반으로 선택된 LLM provider에서 리뷰 텍스트를 생성한다.

    messages 형식은 OpenAI ChatCompletion API 스타일({"role", "content"})을 따른다.
    내부에서는 LangChain 메시지 타입으로 변환한 뒤, provider별 Chat 모델을 호출한다.
    """

    lc_messages = _to_langchain_messages(messages)

    # temperature는 리뷰 결과의 일관성을 위해 1.0으로 고정한다.
    model = _get_llm_model()
    llm = _create_llm(model=model, temperature=1.0)

    response = llm.invoke(lc_messages)
    return response.content.strip()
