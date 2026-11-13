import wave
from pathlib import Path

import numpy as np
from pydub import AudioSegment

from audio_overview.speech.stitch import chapters_from, render_speech, write_audio
from audio_overview.speech.tone import ToneEngine
from audio_overview.types import ScriptLine


def _f0(samples: np.ndarray, sample_rate: int) -> float:
    window = samples[:sample_rate]
    window = window - window.mean()
    corr = np.correlate(window, window, mode="full")
    corr = corr[len(corr) // 2 :]
    low = int(sample_rate / 300)
    high = int(sample_rate / 70)
    lag = low + int(np.argmax(corr[low:high]))
    return sample_rate / lag


def test_two_tone_voices_differ_and_are_not_silent() -> None:
    engine = ToneEngine()
    female = engine.synthesize("The workshop opened in nineteen ninety eight.", "af_heart")
    male = engine.synthesize("The workshop opened in nineteen ninety eight.", "am_michael")
    assert female.shape == male.shape
    assert float(np.sqrt(np.mean(female**2))) > 0.05
    assert abs(_f0(female, engine.sample_rate) - 220) < 5
    assert abs(_f0(male, engine.sample_rate) - 110) < 5


def test_stitch_inserts_a_longer_pause_between_sections() -> None:
    engine = ToneEngine()
    lines = (
        ScriptLine("Maya", "One short line.", "Room"),
        ScriptLine("Leo", "Another short line.", "Room"),
        ScriptLine("Maya", "A later section.", "Basin"),
    )
    segment, timed = render_speech(
        lines,
        engine,
        {"Maya": "af_heart", "Leo": "am_michael"}.__getitem__,
        pause_ms=200,
        section_pause_ms=500,
    )
    gap_same = timed[1].start_ms - (timed[0].start_ms + timed[0].duration_ms)
    gap_section = timed[2].start_ms - (timed[1].start_ms + timed[1].duration_ms)
    assert gap_same == 200
    assert gap_section == 500
    spoken = sum(item.duration_ms for item in timed)
    assert len(segment) == spoken + 200 + 500
    chapters = chapters_from(timed, len(segment))
    assert [chapter.title for chapter in chapters] == ["Room", "Basin"]
    assert chapters[0].start_ms == 0
    assert chapters[0].end_ms <= chapters[1].start_ms
    assert chapters[-1].end_ms == len(segment)


def test_mp3_and_wav_round_trip(tmp_path: Path) -> None:
    engine = ToneEngine()
    lines = (
        ScriptLine("Maya", "Hello from the first host.", "Opening"),
        ScriptLine("Leo", "Hello from the second host.", "Opening"),
    )
    segment, timed = render_speech(
        lines,
        engine,
        {"Maya": "af_heart", "Leo": "am_michael"}.__getitem__,
        pause_ms=100,
        section_pause_ms=100,
    )
    wav_path = tmp_path / "episode.wav"
    mp3_path = tmp_path / "episode.mp3"
    chapters = chapters_from(timed, len(segment))
    write_audio(segment, wav_path, chapters, title="Test", artist="Maya, Leo")
    write_audio(segment, mp3_path, chapters, title="Test", artist="Maya, Leo")
    with wave.open(str(wav_path)) as handle:
        assert handle.getnchannels() == 1
        assert handle.getframerate() == 24000
    loaded = AudioSegment.from_mp3(mp3_path)
    assert abs(len(loaded) - len(segment)) < 400
    assert loaded.rms > 100
    assert mp3_path.stat().st_size > 1000
