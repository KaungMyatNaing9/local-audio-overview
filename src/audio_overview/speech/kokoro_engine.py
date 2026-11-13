"""Kokoro ONNX speech, the default engine.

Kokoro-82M weights are Apache-2.0. The ``kokoro-onnx`` runtime is MIT.
Both are published by their authors; this package does not vendor the files.
Piper was not chosen: the current ``piper-tts`` package is GPL-3.0, and several
of its voices are non-commercial. The ``SpeechEngine`` shape is one method,
``synthesize(text, voice) -> float32 mono samples``, so another engine can be
added beside this one.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from audio_overview.errors import AudioOverviewError
from audio_overview.speech.voices import is_english_voice, lang_for_voice, list_voice_names


class KokoroEngine:
    name = "kokoro"
    sample_rate = 24_000

    def __init__(
        self,
        model_path: Path,
        voices_path: Path,
        *,
        speed: float = 1.0,
        language: str | None = None,
    ) -> None:
        self.model_path = model_path
        self.voices_path = voices_path
        self.speed = speed
        self.language = language
        self._known = set(list_voice_names(voices_path))
        try:
            from kokoro_onnx import Kokoro
        except ImportError as exc:
            raise AudioOverviewError(
                "Kokoro is not installed. Install it with: pip install 'audio-overview[kokoro]'"
            ) from exc
        try:
            self._kokoro = Kokoro(str(model_path), str(voices_path))
        except Exception as exc:
            raise AudioOverviewError(f"Could not load Kokoro from {model_path}: {exc}") from exc

    def synthesize(self, text: str, voice: str) -> np.ndarray:
        if voice not in self._known:
            raise AudioOverviewError(f"Unknown Kokoro voice {voice!r}. Run: audio-overview list-voices")
        if not is_english_voice(voice):
            lang_for_voice(voice)
        spoken = " ".join(text.split())
        if not spoken:
            raise AudioOverviewError("Refusing to synthesize an empty turn.")
        lang = lang_for_voice(voice, self.language)
        try:
            samples, rate = self._kokoro.create(
                spoken,
                voice=voice,
                speed=self.speed,
                lang=lang,
            )
        except Exception as exc:
            raise AudioOverviewError(f"Kokoro failed on a {voice} turn: {exc}") from exc
        if rate != self.sample_rate:
            raise AudioOverviewError(f"Kokoro returned sample rate {rate}, expected {self.sample_rate}.")
        audio = np.asarray(samples, dtype=np.float32).reshape(-1)
        if audio.size == 0:
            raise AudioOverviewError(f"Kokoro returned no samples for voice {voice}.")
        return audio
