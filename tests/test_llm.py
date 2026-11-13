import json

import pytest

from audio_overview.errors import AudioOverviewError
from audio_overview.script.llm import OpenAICompatibleBackend, normalize_base_url


def test_base_url_gains_a_v1_suffix() -> None:
    assert normalize_base_url("http://127.0.0.1:11434") == "http://127.0.0.1:11434/v1"
    assert normalize_base_url("https://example.test/v1/") == "https://example.test/v1"


def test_transport_sees_the_model_and_optional_key() -> None:
    seen: dict[str, object] = {}

    def transport(url: str, payload: dict, headers: dict, timeout: float) -> str:
        seen["url"] = url
        seen["payload"] = payload
        seen["headers"] = headers
        seen["timeout"] = timeout
        return json.dumps({"choices": [{"message": {"content": "hello from the model"}}]})

    backend = OpenAICompatibleBackend(
        base_url="http://127.0.0.1:11434",
        model="llama3.2",
        api_key="secret",
        timeout=12,
        transport=transport,
        name="ollama",
    )
    assert backend.complete([{"role": "user", "content": "hi"}]) == "hello from the model"
    assert seen["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    payload = seen["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "llama3.2"
    assert payload["messages"][0]["content"] == "hi"
    headers = seen["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer secret"


def test_missing_key_omits_the_auth_header() -> None:
    seen: dict[str, dict] = {}

    def transport(url: str, payload: dict, headers: dict, timeout: float) -> str:
        seen["headers"] = headers
        return json.dumps({"choices": [{"message": {"content": "ok"}}]})

    backend = OpenAICompatibleBackend(
        base_url="http://localhost:8080/v1",
        model="local",
        transport=transport,
    )
    backend.complete([{"role": "user", "content": "hi"}])
    assert "Authorization" not in seen["headers"]


def test_error_payload_is_reported() -> None:
    def transport(url: str, payload: dict, headers: dict, timeout: float) -> str:
        return json.dumps({"error": {"message": "model not found"}})

    backend = OpenAICompatibleBackend(
        base_url="http://127.0.0.1:11434/v1",
        model="missing",
        transport=transport,
    )
    with pytest.raises(AudioOverviewError, match="model not found"):
        backend.complete([{"role": "user", "content": "hi"}])
