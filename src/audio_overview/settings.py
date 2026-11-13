"""Run options, including the environment variables the CLI reads."""

from __future__ import annotations

import os
from dataclasses import dataclass

from audio_overview.errors import AudioOverviewError

LENGTHS = ("short", "medium", "long")
TONES = ("conversational", "explanatory", "skeptical", "enthusiastic")
BACKENDS = ("fake", "ollama", "openai")
ENGINES = ("kokoro", "tone")
LANGUAGES = ("en-us", "en-gb")

ENV_BASE_URL = "AUDIO_OVERVIEW_BASE_URL"
ENV_MODEL = "AUDIO_OVERVIEW_MODEL"
ENV_API_KEY = "AUDIO_OVERVIEW_API_KEY"
ENV_BACKEND = "AUDIO_OVERVIEW_BACKEND"
ENV_TIMEOUT = "AUDIO_OVERVIEW_TIMEOUT"
ENV_MODEL_DIR = "AUDIO_OVERVIEW_MODEL_DIR"
ENV_KOKORO_MODEL = "AUDIO_OVERVIEW_KOKORO_MODEL"
ENV_KOKORO_VOICES = "AUDIO_OVERVIEW_KOKORO_VOICES"


@dataclass
class Settings:
    length: str = "short"
    tone: str = "conversational"
    host_a: str = "Maya"
    host_b: str = "Leo"
    voice_a: str = "af_heart"
    voice_b: str = "am_michael"
    backend: str = "fake"
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    tts: str = "kokoro"
    language: str | None = None
    replay: str | None = None
    repair: bool = True
    strict: bool = False
    chunk_chars: int = 4000
    chunk_overlap: int = 200
    speech_rate: float = 1.0
    pause_ms: int = 380
    section_pause_ms: int = 650
    timeout: float = 180.0
    quiet: bool = False

    def validate(self) -> None:
        if self.length not in LENGTHS:
            raise AudioOverviewError(f"length must be one of: {', '.join(LENGTHS)}")
        if self.tone not in TONES:
            raise AudioOverviewError(f"tone must be one of: {', '.join(TONES)}")
        if self.backend not in BACKENDS:
            raise AudioOverviewError(f"backend must be one of: {', '.join(BACKENDS)}")
        if self.tts not in ENGINES:
            raise AudioOverviewError(f"tts must be one of: {', '.join(ENGINES)}")
        if self.language is not None and self.language not in LANGUAGES:
            raise AudioOverviewError(
                "V1 speech is English only (en-us or en-gb). Other Kokoro voices "
                "are in the voice file, but this release only phonemizes English."
            )
        if not self.host_a.strip() or not self.host_b.strip():
            raise AudioOverviewError("Host names cannot be empty.")
        if self.host_a.strip().lower() == self.host_b.strip().lower():
            raise AudioOverviewError("The two hosts need different names.")
        if not self.voice_a.strip() or not self.voice_b.strip():
            raise AudioOverviewError("Voice ids cannot be empty.")
        if not 0.5 <= self.speech_rate <= 2.0:
            raise AudioOverviewError("speech rate must be between 0.5 and 2.0.")
        if self.chunk_chars < 200:
            raise AudioOverviewError("chunk size must be at least 200 characters.")
        if self.chunk_overlap < 0 or self.chunk_overlap >= self.chunk_chars:
            raise AudioOverviewError("overlap must be zero or smaller than the chunk size.")
        if self.pause_ms < 0 or self.section_pause_ms < 0:
            raise AudioOverviewError("pauses cannot be negative.")
        if self.timeout <= 0:
            raise AudioOverviewError("timeout must be positive.")
        self.host_a = self.host_a.strip()
        self.host_b = self.host_b.strip()
        self.voice_a = self.voice_a.strip()
        self.voice_b = self.voice_b.strip()


def apply_env(settings: Settings) -> Settings:
    """Fill connection fields from the environment when the CLI left them unset.

    The backend name itself is chosen in the CLI: an explicit ``--backend``
    wins, otherwise ``AUDIO_OVERVIEW_BACKEND``, otherwise ``fake``.
    """

    model = settings.model or os.environ.get(ENV_MODEL) or None
    base_url = settings.base_url or os.environ.get(ENV_BASE_URL) or None
    api_key = settings.api_key or os.environ.get(ENV_API_KEY) or None
    timeout = settings.timeout
    raw_timeout = os.environ.get(ENV_TIMEOUT)
    if raw_timeout and settings.timeout == 180.0:
        try:
            timeout = float(raw_timeout)
        except ValueError as exc:
            raise AudioOverviewError(f"{ENV_TIMEOUT} must be a number of seconds.") from exc
    if settings.backend == "ollama" and not base_url:
        base_url = "http://127.0.0.1:11434/v1"
    if settings.backend == "ollama" and not model:
        model = "llama3.2"
    if settings.backend == "openai" and not base_url:
        raise AudioOverviewError(
            f"The openai backend needs --base-url or {ENV_BASE_URL} (an OpenAI-compatible /v1 root)."
        )
    if settings.backend == "openai" and not model:
        raise AudioOverviewError(f"The openai backend needs --model or {ENV_MODEL}.")
    settings.model = model
    settings.base_url = base_url
    settings.api_key = api_key
    settings.timeout = timeout
    settings.validate()
    return settings
