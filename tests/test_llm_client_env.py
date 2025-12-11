from typing import Any

import pytest

from src import llm_client


class _DummyResponse:
    def __init__(self, content: str) -> None:
        self.content = content


class _DummyChatModel:
    """실제 LLM 호출을 막고, env 기반 설정/메시지 전달 여부만 검증하기 위한 더미 모델."""

    last_init_kwargs: dict[str, Any] | None = None
    last_invoked_messages: list[Any] | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # noqa: D401, ANN401
        _DummyChatModel.last_init_kwargs = kwargs

    def invoke(self, messages: list[Any]) -> _DummyResponse:  # noqa: D401, ANN401
        _DummyChatModel.last_invoked_messages = messages
        return _DummyResponse("dummy-response")


def test_create_llm_openai_uses_chatopenai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OPENAI provider 설정 시 env를 이용해 ChatOpenAI 기반 LLM 클라이언트를 생성하는지 검증한다."""

    _DummyChatModel.last_init_kwargs = None
    _DummyChatModel.last_invoked_messages = None

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)

    monkeypatch.setattr(llm_client, "ChatOpenAI", _DummyChatModel)

    llm = llm_client._create_llm(model="gpt-5-mini", temperature=0.5)

    assert isinstance(llm, _DummyChatModel)
    assert _DummyChatModel.last_init_kwargs is not None
    assert _DummyChatModel.last_init_kwargs["model"] == "gpt-5-mini"
    assert _DummyChatModel.last_init_kwargs["api_key"] == "test-key"
    assert "base_url" not in _DummyChatModel.last_init_kwargs


def test_create_llm_gemini_uses_chatgoogle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GEMINI provider 설정 시 env를 이용해 ChatGoogleGenerativeAI 기반 LLM 클라이언트를 생성하는지 검증한다."""

    _DummyChatModel.last_init_kwargs = None
    _DummyChatModel.last_invoked_messages = None

    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)

    monkeypatch.setattr(llm_client, "ChatGoogleGenerativeAI", _DummyChatModel)

    llm = llm_client._create_llm(model="gemini-1.5-flash", temperature=0.3)

    assert isinstance(llm, _DummyChatModel)
    assert _DummyChatModel.last_init_kwargs is not None
    assert _DummyChatModel.last_init_kwargs["model"] == "gemini-1.5-flash"
    assert _DummyChatModel.last_init_kwargs["api_key"] == "test-key"


def test_create_llm_ollama_uses_chatollama(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OLLAMA provider 설정 시 env를 이용해 ChatOllama 기반 LLM 클라이언트를 생성하는지 검증한다."""

    _DummyChatModel.last_init_kwargs = None
    _DummyChatModel.last_invoked_messages = None

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434")
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)

    monkeypatch.setattr(llm_client, "ChatOllama", _DummyChatModel)

    llm = llm_client._create_llm(model="llama2", temperature=0.7)

    assert isinstance(llm, _DummyChatModel)
    assert _DummyChatModel.last_init_kwargs is not None
    assert _DummyChatModel.last_init_kwargs["model"] == "llama2"
    assert _DummyChatModel.last_init_kwargs["base_url"] == "http://localhost:11434"
    assert "request_timeout" in _DummyChatModel.last_init_kwargs


def test_create_llm_openrouter_uses_chatopenai_with_openrouter_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OPENROUTER provider 설정 시 env를 이용해 ChatOpenAI(OpenRouter endpoint) 기반 LLM 클라이언트를 생성하는지 검증한다."""

    _DummyChatModel.last_init_kwargs = None
    _DummyChatModel.last_invoked_messages = None

    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("LLM_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("OPENROUTER_BASE_URL", raising=False)

    monkeypatch.setattr(llm_client, "ChatOpenAI", _DummyChatModel)

    llm = llm_client._create_llm(
        model="openrouter-test-model",
        temperature=0.9,
    )

    assert isinstance(llm, _DummyChatModel)
    assert _DummyChatModel.last_init_kwargs is not None
    assert _DummyChatModel.last_init_kwargs["model"] == "openrouter-test-model"
    assert _DummyChatModel.last_init_kwargs["api_key"] == "test-key"
    assert (
        _DummyChatModel.last_init_kwargs["base_url"] == "https://openrouter.ai/api/v1"
    )


def test_create_llm_invalid_provider_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """지원하지 않는 LLM_PROVIDER 값이 설정된 경우 예외를 발생시키는지 검증한다."""

    monkeypatch.setenv("LLM_PROVIDER", "unknown-provider")

    with pytest.raises(ValueError):
        llm_client._create_llm(model="dummy-model", temperature=0.5)
