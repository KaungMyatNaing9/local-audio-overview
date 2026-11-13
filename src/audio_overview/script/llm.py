"""OpenAI-compatible chat client. Ollama's ``/v1`` API is the same shape."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from audio_overview.errors import AudioOverviewError

Transport = Callable[[str, dict[str, Any], dict[str, str], float], str]


class OpenAICompatibleBackend:
    """POST ``/chat/completions`` and return the assistant text."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 180.0,
        temperature: float = 0.3,
        max_tokens: int = 1800,
        name: str = "openai",
        transport: Transport | None = None,
    ) -> None:
        self.name = name
        self.base_url = normalize_base_url(base_url)
        self.model = model
        self.api_key = api_key
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._transport = transport or _urllib_transport

    def complete(self, messages: list[dict[str, str]]) -> str:
        url = self.base_url + "/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        try:
            raw = self._transport(url, payload, headers, self.timeout)
        except AudioOverviewError:
            raise
        except Exception as exc:
            raise AudioOverviewError(f"Could not reach the language model at {url}: {exc}") from exc
        return _assistant_text(raw)


def normalize_base_url(url: str) -> str:
    cleaned = url.strip().rstrip("/")
    if not cleaned:
        raise AudioOverviewError("The language model base URL is empty.")
    if cleaned.endswith("/v1"):
        return cleaned
    return cleaned + "/v1"


def _assistant_text(raw: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AudioOverviewError("The language model did not return JSON.") from exc
    if isinstance(data, dict) and data.get("error"):
        error = data["error"]
        message = error.get("message") if isinstance(error, dict) else str(error)
        raise AudioOverviewError(f"The language model refused the request: {message}")
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AudioOverviewError("The language model response has no message content.") from exc
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(str(part["text"]))
        content = "\n".join(parts)
    if not isinstance(content, str) or not content.strip():
        raise AudioOverviewError("The language model returned an empty script.")
    return content


def _urllib_transport(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: float) -> str:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise AudioOverviewError(
            f"The language model returned HTTP {exc.code}: {detail or exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise AudioOverviewError(f"Could not reach the language model at {url}: {exc.reason}") from exc
