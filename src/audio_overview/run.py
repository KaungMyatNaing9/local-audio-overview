"""Load a source, write a script, and render the episode."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from audio_overview.errors import AudioOverviewError, GroundingRejected
from audio_overview.ingest.load import load_source
from audio_overview.ingest.web import Fetcher
from audio_overview.output import format_duration, write_sidecars
from audio_overview.script.fake import FakeBackend
from audio_overview.script.grounding import format_flag_report
from audio_overview.script.llm import OpenAICompatibleBackend
from audio_overview.script.pipeline import LanguageBackend, write_script
from audio_overview.script.schema import parse_script
from audio_overview.settings import Settings
from audio_overview.speech.kokoro_engine import KokoroEngine
from audio_overview.speech.stitch import chapters_from, render_speech, write_audio
from audio_overview.speech.tone import ToneEngine
from audio_overview.speech.voices import resolve_kokoro_paths
from audio_overview.types import Document, ScriptDraft

_MAX_TOKENS = {"short": 900, "medium": 1800, "long": 3200}


@dataclass(frozen=True)
class EpisodeResult:
    document: Document
    draft: ScriptDraft
    output: Path
    duration_ms: int
    paths: dict[str, Path]


def run_episode(
    source: str,
    output: Path,
    settings: Settings,
    *,
    fetcher: Fetcher | None = None,
    backend: LanguageBackend | None = None,
    engine: ToneEngine | KokoroEngine | None = None,
) -> EpisodeResult:
    settings.validate()
    document = load_source(source, fetcher=fetcher)
    _say(
        settings,
        f"source: {document.kind} · {document.title} · {document.word_count} words · {document.source}",
    )
    model = backend if backend is not None else build_backend(settings, document)
    draft = write_script(document, model, settings)
    _say(
        settings,
        "script: "
        f"{draft.backend} · {settings.length} · {settings.tone} · "
        f"{settings.host_a}, {settings.host_b} · {len(draft.lines)} lines",
    )
    if draft.repaired:
        _say(settings, "script: one repair pass after the grounding check")
    if draft.flags:
        _say(settings, format_flag_report(draft.flags))
    else:
        _say(
            settings,
            "grounding: 0 flags (numbers, quotations, and proper names only)",
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    if settings.strict and draft.flags:
        paths = write_sidecars(output, document, draft, settings, None, None, None)
        _say(settings, f"wrote: {paths['script']}")
        _say(settings, f"wrote: {paths['grounding']}")
        raise GroundingRejected("Grounding flags remain and --strict is set, so no audio was written.")
    speech = engine if engine is not None else build_engine(settings)
    _say(settings, f"speech: {speech.name} · {settings.voice_a}, {settings.voice_b}")
    segment, timed = render_speech(
        draft.lines,
        speech,
        _voice_for(settings),
        pause_ms=settings.pause_ms,
        section_pause_ms=settings.section_pause_ms,
    )
    chapters = chapters_from(timed, len(segment))
    paths = write_sidecars(output, document, draft, settings, timed, chapters, len(segment))
    write_audio(
        segment,
        output,
        chapters,
        title=document.title,
        artist=f"{settings.host_a}, {settings.host_b}",
    )
    _say(settings, f"wrote: {output} ({format_duration(len(segment))})")
    for key in ("transcript", "chapters", "script", "grounding"):
        _say(settings, f"wrote: {paths[key]}")
    return EpisodeResult(document, draft, output, len(segment), paths)


def build_backend(settings: Settings, document: Document) -> LanguageBackend:
    if settings.backend == "fake":
        replay = None
        if settings.replay:
            path = Path(settings.replay)
            if not path.is_file():
                raise AudioOverviewError(f"Replay script not found: {path}")
            replay = parse_script(path.read_text(encoding="utf-8"), settings.host_a, settings.host_b)
        return FakeBackend(document, replay=replay)
    if settings.backend in {"ollama", "openai"}:
        if not settings.base_url or not settings.model:
            raise AudioOverviewError("The language model backend needs a base URL and a model name.")
        return OpenAICompatibleBackend(
            base_url=settings.base_url,
            model=settings.model,
            api_key=settings.api_key,
            timeout=settings.timeout,
            max_tokens=_MAX_TOKENS[settings.length],
            name=settings.backend,
        )
    raise AudioOverviewError(f"Unknown backend {settings.backend}.")


def build_engine(settings: Settings) -> ToneEngine | KokoroEngine:
    if settings.tts == "tone":
        return ToneEngine()
    if settings.tts != "kokoro":
        raise AudioOverviewError(f"Unknown speech engine {settings.tts}.")
    model_path, voices_path = _kokoro_files()
    return KokoroEngine(
        model_path,
        voices_path,
        speed=settings.speech_rate,
        language=settings.language,
    )


def _kokoro_files() -> tuple[Path, Path]:
    model_path, voices_path = resolve_kokoro_paths("full")
    if not model_path.is_file():
        int8_path, int8_voices = resolve_kokoro_paths("int8")
        if int8_path.is_file():
            model_path = int8_path
            if not voices_path.is_file():
                voices_path = int8_voices
    if not model_path.is_file() or not voices_path.is_file():
        raise AudioOverviewError(
            "Kokoro model files were not found.\n"
            f"Looked for the model at {model_path}\n"
            f"and the voices at {voices_path}.\n"
            "Run: audio-overview download-models"
        )
    return model_path, voices_path


def _voice_for(settings: Settings):
    mapping = {settings.host_a: settings.voice_a, settings.host_b: settings.voice_b}

    def voice_for(speaker: str) -> str:
        try:
            return mapping[speaker]
        except KeyError as exc:
            raise AudioOverviewError(f"No voice configured for {speaker}.") from exc

    return voice_for


def _say(settings: Settings, message: str) -> None:
    if not settings.quiet:
        print(message, file=sys.stderr)
