"""Command line for Local Audio Overview."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from audio_overview import __version__
from audio_overview.errors import AudioOverviewError, GroundingRejected
from audio_overview.run import run_episode
from audio_overview.settings import (
    BACKENDS,
    ENGINES,
    ENV_BACKEND,
    LANGUAGES,
    LENGTHS,
    TONES,
    Settings,
    apply_env,
)
from audio_overview.speech.voices import (
    download_models,
    is_english_voice,
    list_voice_names,
    resolve_kokoro_paths,
)

_EPILOG = """\
examples:
  audio-overview notes.md -o episode.mp3 --backend fake --tts tone
  audio-overview paper.pdf -o episode.mp3 --length short --backend ollama --model llama3.2
  audio-overview https://example.com/story -o episode.mp3 --base-url http://127.0.0.1:8080/v1 --model local
  audio-overview ./my-repo -o episode.mp3 --host-a Mina --host-b Jules
  audio-overview download-models
  audio-overview list-voices

The default backend is fake: a grounded read-through that does not call a model.
Set --backend ollama or --backend openai for a generated conversation.
""".rstrip()


class _Help(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
    pass


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] in {"-h", "--help"}:
        _run_parser().print_help()
        return 0
    if args[0] in {"-V", "--version"}:
        print(f"audio-overview {__version__}")
        return 0
    if args[0] == "download-models":
        return _download(args[1:])
    if args[0] == "list-voices":
        return _list_voices(args[1:])
    try:
        return _run(args)
    except GroundingRejected as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except AudioOverviewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _run(argv: list[str]) -> int:
    parser = _run_parser()
    namespace = parser.parse_args(argv)
    backend = namespace.backend or os.environ.get(ENV_BACKEND) or "fake"
    settings = Settings(
        length=namespace.length,
        tone=namespace.tone,
        host_a=namespace.host_a,
        host_b=namespace.host_b,
        voice_a=namespace.voice_a,
        voice_b=namespace.voice_b,
        backend=backend,
        model=namespace.model,
        base_url=namespace.base_url,
        api_key=namespace.api_key,
        tts=namespace.tts,
        language=namespace.language,
        replay=namespace.replay,
        repair=not namespace.no_repair and not namespace.replay,
        strict=namespace.strict,
        chunk_chars=namespace.chunk_chars,
        chunk_overlap=namespace.overlap,
        speech_rate=namespace.speech_rate,
        pause_ms=namespace.pause_ms,
        section_pause_ms=namespace.section_pause_ms,
        quiet=namespace.quiet,
    )
    apply_env(settings)
    if settings.voice_a == settings.voice_b and not settings.quiet:
        print("warning: both hosts use the same voice.", file=sys.stderr)
    run_episode(namespace.source, Path(namespace.output), settings)
    return 0


def _download(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="audio-overview download-models",
        description="Download Kokoro ONNX weights into the local cache.",
        formatter_class=_Help,
    )
    parser.add_argument("--dir", type=Path, default=None, help="directory to write the files into")
    parser.add_argument("--variant", choices=("full", "int8"), default="full")
    parser.add_argument("--force", action="store_true", help="download again even if the files exist")
    namespace = parser.parse_args(argv)
    try:
        model_path, voices_path = download_models(namespace.dir, namespace.variant, force=namespace.force)
    except AudioOverviewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(model_path)
    print(voices_path)
    return 0


def _list_voices(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="audio-overview list-voices",
        description="List voices in the downloaded Kokoro voices file.",
        formatter_class=_Help,
    )
    parser.add_argument("--voices", type=Path, default=None, help="path to voices-v1.0.bin")
    namespace = parser.parse_args(argv)
    path = namespace.voices or resolve_kokoro_paths()[1]
    try:
        names = list_voice_names(path)
    except AudioOverviewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    english = [name for name in names if is_english_voice(name)]
    other = [name for name in names if not is_english_voice(name)]
    print(f"English voices V1 can speak ({len(english)}), from {path}:")
    for name in english:
        print(f"  {name}")
    if other:
        print(f"Other voices in the file ({len(other)}) are not synthesized in V1:")
        for name in other:
            print(f"  {name}")
    return 0


def _run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audio-overview",
        description="Turn a PDF, web page, text file, or local git repo into a two-host MP3.",
        epilog=_EPILOG,
        formatter_class=_Help,
    )
    parser.add_argument("source", help="PDF, URL, markdown/text file, or directory")
    parser.add_argument("-o", "--output", required=True, help="output .mp3 or .wav path")
    parser.add_argument("--length", choices=LENGTHS, default="short")
    parser.add_argument("--tone", choices=TONES, default="conversational")
    parser.add_argument("--host-a", default="Maya")
    parser.add_argument("--host-b", default="Leo")
    parser.add_argument("--voice-a", default="af_heart", help="Kokoro voice id for host A")
    parser.add_argument("--voice-b", default="am_michael", help="Kokoro voice id for host B")
    parser.add_argument(
        "--backend",
        choices=BACKENDS,
        default=None,
        help="fake, ollama, or openai. Default: AUDIO_OVERVIEW_BACKEND or fake",
    )
    parser.add_argument("--model", default=None, help="model name for ollama or openai")
    parser.add_argument(
        "--base-url",
        default=None,
        help="OpenAI-compatible /v1 root. Ollama default is http://127.0.0.1:11434/v1",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key. Prefer AUDIO_OVERVIEW_API_KEY so it stays out of the process list",
    )
    parser.add_argument("--tts", choices=ENGINES, default="kokoro")
    parser.add_argument(
        "--language",
        choices=LANGUAGES,
        default=None,
        help="phoneme language. Default follows the voice: en-us or en-gb",
    )
    parser.add_argument(
        "--replay",
        default=None,
        help="JSONL script to speak with the fake backend instead of the read-through",
    )
    parser.add_argument("--strict", action="store_true", help="stop before audio if grounding flags remain")
    parser.add_argument(
        "--no-repair",
        action="store_true",
        help="do not ask the model to rewrite flagged lines",
    )
    parser.add_argument("--chunk-chars", type=int, default=4000)
    parser.add_argument("--overlap", type=int, default=200)
    parser.add_argument("--speech-rate", type=float, default=1.0, help="Kokoro speed, from 0.5 to 2.0")
    parser.add_argument("--pause-ms", type=int, default=380, help="silence between turns in one section")
    parser.add_argument("--section-pause-ms", type=int, default=650, help="silence when the section changes")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("-V", "--version", action="version", version=f"audio-overview {__version__}")
    return parser
