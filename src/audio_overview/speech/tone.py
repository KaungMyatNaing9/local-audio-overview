"""A sine-wave engine for tests and for trying the pipeline without a model.

It is not speech. Each voice is a steady tone so tests can tell the hosts apart.
"""

from __future__ import annotations

import zlib

import numpy as np

from audio_overview.errors import AudioOverviewError


class ToneEngine:
    name = "tone"
    sample_rate = 24_000

    def synthesize(self, text: str, voice: str) -> np.ndarray:
        words = max(1, len(text.split()))
        duration = min(8.0, max(0.3, 0.18 * words))
        count = int(self.sample_rate * duration)
        if count <= 0:
            raise AudioOverviewError("Refusing to synthesize an empty turn.")
        time = np.arange(count, dtype=np.float32) / self.sample_rate
        tone = (0.25 * np.sin(2 * np.pi * _frequency(voice) * time)).astype(np.float32)
        fade = min(120, count // 4)
        if fade > 0:
            ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)
            tone[:fade] *= ramp
            tone[-fade:] *= ramp[::-1]
        return tone


def _frequency(voice: str) -> float:
    if voice.startswith(("af_", "bf_", "ef_", "ff_", "hf_", "if_", "jf_", "pf_", "zf_")):
        return 220.0
    if voice.startswith(("am_", "bm_", "em_", "hm_", "im_", "jm_", "pm_", "zm_")):
        return 110.0
    slot = zlib.adler32(voice.encode()) % 9
    return 130.0 + slot * 15.0
