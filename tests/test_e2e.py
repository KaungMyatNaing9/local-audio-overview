import json
from pathlib import Path

import numpy as np
import pytest

from audio_overview.run import run_episode
from audio_overview.settings import Settings
from audio_overview.speech.kokoro_engine import KokoroEngine
from audio_overview.speech.voices import resolve_kokoro_paths
from tests.conftest import SAMPLE, SAMPLE_SCRIPT


def test_end_to_end_fake_script_and_stub_speech(tmp_path: Path) -> None:
    source = tmp_path / "notes.md"
    source.write_text(
        "# Basin notes\n\n## The barrel\n\nThe rain barrel is behind the building. "
        "It was repaired in 1998.\n",
        encoding="utf-8",
    )
    output = tmp_path / "episode.mp3"
    result = run_episode(
        str(source),
        output,
        Settings(length="short", backend="fake", tts="tone", quiet=True, repair=True),
    )
    assert output.is_file()
    assert result.duration_ms > 500
    assert result.draft.flags == ()
    transcript = result.paths["transcript"].read_text(encoding="utf-8")
    assert "Maya" in transcript
    assert "Leo" in transcript
    assert "1998" in transcript
    chapters = json.loads(result.paths["chapters"].read_text(encoding="utf-8"))
    assert chapters["chapters"]
    grounding = json.loads(result.paths["grounding"].read_text(encoding="utf-8"))
    assert grounding["flag_count"] == 0


def test_replay_script_through_the_runner(tmp_path: Path) -> None:
    output = tmp_path / "episode.wav"
    result = run_episode(
        str(SAMPLE),
        output,
        Settings(
            backend="fake",
            tts="tone",
            replay=str(SAMPLE_SCRIPT),
            repair=False,
            quiet=True,
        ),
    )
    assert result.draft.flags == ()
    assert len(result.draft.lines) == 12
    assert output.stat().st_size > 1000


def _kokoro_ready() -> bool:
    model, voices = resolve_kokoro_paths("full")
    return model.is_file() and voices.is_file()


@pytest.mark.skipif(not _kokoro_ready(), reason="Kokoro weights are not downloaded")
def test_kokoro_two_voices_are_audible_and_distinct() -> None:
    model, voices = resolve_kokoro_paths("full")
    engine = KokoroEngine(model, voices)
    text = "The workshop at 18 Warder Street opened in 1998."
    female = engine.synthesize(text, "af_heart")
    male = engine.synthesize(text, "am_michael")
    assert _rms(female) > 0.01
    assert _rms(male) > 0.01
    assert abs(_f0(female, engine.sample_rate) - _f0(male, engine.sample_rate)) > 20


def _rms(samples: np.ndarray) -> float:
    audio = np.asarray(samples, dtype=np.float64)
    return float(np.sqrt(np.mean(audio * audio)))


def _f0(samples: np.ndarray, sample_rate: int) -> float:
    window = np.asarray(samples[:sample_rate], dtype=np.float64)
    window = window - window.mean()
    corr = np.correlate(window, window, mode="full")
    corr = corr[len(corr) // 2 :]
    low = int(sample_rate / 320)
    high = int(sample_rate / 70)
    lag = low + int(np.argmax(corr[low:high]))
    return sample_rate / lag
