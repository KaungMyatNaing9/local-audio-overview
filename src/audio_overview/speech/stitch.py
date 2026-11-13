"""Join turns with pauses and write one WAV or MP3."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np
from pydub import AudioSegment

from audio_overview.errors import AudioOverviewError
from audio_overview.types import Chapter, ScriptLine, TimedLine


class SpeechEngine:
    """Structural type, written out so other engines stay obvious.

    ``synthesize`` returns mono float32 samples in ``[-1, 1]`` at ``sample_rate``.
    """

    name: str
    sample_rate: int

    def synthesize(self, text: str, voice: str) -> np.ndarray: ...


def render_speech(
    lines: Sequence[ScriptLine],
    engine: SpeechEngine,
    voice_for: Callable[[str], str],
    *,
    pause_ms: int,
    section_pause_ms: int,
) -> tuple[AudioSegment, list[TimedLine]]:
    if not lines:
        raise AudioOverviewError("The script has no lines to speak.")
    pieces: list[AudioSegment] = []
    timed: list[TimedLine] = []
    cursor = 0
    previous: str | None = None
    for line in lines:
        if timed:
            gap = section_pause_ms if line.section != previous else pause_ms
            pieces.append(AudioSegment.silent(duration=gap, frame_rate=engine.sample_rate))
            cursor += gap
        samples = np.asarray(engine.synthesize(line.text, voice_for(line.speaker)), dtype=np.float32)
        samples = samples.reshape(-1)
        if samples.size == 0 or _rms(samples) < 1e-3:
            raise AudioOverviewError(f"Speech for {line.speaker} was silent.")
        segment = _segment(samples, engine.sample_rate)
        duration = len(segment)
        timed.append(TimedLine(line, cursor, duration))
        pieces.append(segment)
        cursor += duration
        previous = line.section
    episode = pieces[0]
    for piece in pieces[1:]:
        episode += piece
    return episode, timed


def chapters_from(timed: Sequence[TimedLine], total_ms: int) -> list[Chapter]:
    chapters: list[Chapter] = []
    for item in timed:
        title = item.line.section or "Overview"
        end = item.start_ms + item.duration_ms
        if not chapters or chapters[-1].title != title:
            chapters.append(Chapter(title, item.start_ms, end))
        else:
            current = chapters[-1]
            chapters[-1] = Chapter(current.title, current.start_ms, end)
    if chapters and total_ms > chapters[-1].end_ms:
        last = chapters[-1]
        chapters[-1] = Chapter(last.title, last.start_ms, total_ms)
    return [chapter for chapter in chapters if chapter.end_ms > chapter.start_ms]


def write_audio(
    segment: AudioSegment,
    output: Path,
    chapters: Sequence[Chapter],
    *,
    title: str,
    artist: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    suffix = output.suffix.lower()
    if suffix == ".wav":
        segment.export(output, format="wav")
        return
    if suffix != ".mp3":
        raise AudioOverviewError("Output must end in .mp3 or .wav.")
    if shutil.which("ffmpeg") is None:
        raise AudioOverviewError(
            "ffmpeg is required to write MP3 files. Install ffmpeg, or use a .wav output path."
        )
    wav_path = output.with_suffix(".wav.tmp")
    meta_path = output.with_suffix(".ffmeta.tmp")
    try:
        segment.export(wav_path, format="wav")
        meta_path.write_text(_ffmetadata(chapters, title, artist), encoding="utf-8")
        command = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(wav_path),
            "-i",
            str(meta_path),
            "-map",
            "0:a",
            "-map_metadata",
            "1",
            "-map_chapters",
            "1",
            "-codec:a",
            "libmp3lame",
            "-q:a",
            "4",
            str(output),
        ]
        try:
            subprocess.run(command, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or "").strip()
            raise AudioOverviewError(f"ffmpeg failed while writing {output}: {detail}") from exc
    finally:
        wav_path.unlink(missing_ok=True)
        meta_path.unlink(missing_ok=True)


def _segment(samples: np.ndarray, sample_rate: int) -> AudioSegment:
    pcm = np.clip(samples, -1.0, 1.0)
    pcm = (pcm * 32767.0).astype(np.int16)
    return AudioSegment(pcm.tobytes(), frame_rate=sample_rate, sample_width=2, channels=1)


def _rms(samples: np.ndarray) -> float:
    audio = samples.astype(np.float64)
    return float(np.sqrt(np.mean(audio * audio)))


def _ffmetadata(chapters: Sequence[Chapter], title: str, artist: str) -> str:
    lines = [
        ";FFMETADATA1",
        f"title={_meta(title)}",
        f"artist={_meta(artist)}",
        "encoder=audio-overview",
    ]
    for chapter in chapters:
        lines.extend(
            [
                "",
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={max(0, chapter.start_ms)}",
                f"END={max(chapter.start_ms + 1, chapter.end_ms)}",
                f"title={_meta(chapter.title)}",
            ]
        )
    return "\n".join(lines) + "\n"


def _meta(value: str) -> str:
    return value.replace("\\", "\\\\").replace("=", "\\=").replace("#", "\\#").replace(";", "\\;")
