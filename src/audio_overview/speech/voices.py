"""Kokoro voice files: where they live, and which ones V1 can speak."""

from __future__ import annotations

import os
import urllib.request
from collections.abc import Callable
from pathlib import Path

import numpy as np

from audio_overview.errors import AudioOverviewError
from audio_overview.settings import ENV_KOKORO_MODEL, ENV_KOKORO_VOICES, ENV_MODEL_DIR

MODEL_URLS = {
    "full": (
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/kokoro-v1.0.onnx"
    ),
    "int8": (
        "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.int8.onnx"
    ),
}
VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/voices-v1.0.bin"
MODEL_NAMES = {"full": "kokoro-v1.0.onnx", "int8": "kokoro-v1.0.int8.onnx"}
VOICES_NAME = "voices-v1.0.bin"
ENGLISH_PREFIXES = ("af_", "am_", "bf_", "bm_")
_MIN_BYTES = 1_000_000

Fetch = Callable[[str, Path], None]


def model_dir() -> Path:
    override = os.environ.get(ENV_MODEL_DIR)
    if override:
        return Path(override).expanduser()
    return Path.home() / ".cache" / "audio-overview"


def resolve_kokoro_paths(variant: str = "full") -> tuple[Path, Path]:
    if variant not in MODEL_NAMES:
        raise AudioOverviewError("model variant must be full or int8.")
    model = os.environ.get(ENV_KOKORO_MODEL)
    voices = os.environ.get(ENV_KOKORO_VOICES)
    directory = model_dir()
    model_path = Path(model).expanduser() if model else directory / MODEL_NAMES[variant]
    voices_path = Path(voices).expanduser() if voices else directory / VOICES_NAME
    return model_path, voices_path


def is_english_voice(voice: str) -> bool:
    return voice.startswith(ENGLISH_PREFIXES)


def lang_for_voice(voice: str, override: str | None = None) -> str:
    if not is_english_voice(voice):
        raise AudioOverviewError(
            f"Voice {voice!r} is not an English Kokoro voice. "
            "V1 phonemizes en-us and en-gb only "
            "(prefixes af_, am_, bf_, bm_)."
        )
    if override:
        return override
    if voice.startswith(("bf_", "bm_")):
        return "en-gb"
    return "en-us"


def list_voice_names(voices_path: Path) -> list[str]:
    if not voices_path.is_file():
        raise AudioOverviewError(
            f"Voices file not found at {voices_path}. Run: audio-overview download-models"
        )
    try:
        blob = np.load(voices_path)
    except Exception as exc:
        raise AudioOverviewError(f"Could not read voices from {voices_path}: {exc}") from exc
    return sorted(str(name) for name in blob.files)


def download_models(
    dest: Path | None = None,
    variant: str = "full",
    *,
    force: bool = False,
    fetch: Fetch | None = None,
    min_bytes: int = _MIN_BYTES,
) -> tuple[Path, Path]:
    if variant not in MODEL_URLS:
        raise AudioOverviewError("model variant must be full or int8.")
    directory = dest or model_dir()
    directory.mkdir(parents=True, exist_ok=True)
    model_path = directory / MODEL_NAMES[variant]
    voices_path = directory / VOICES_NAME
    getter = fetch or _http_download
    _fetch_one(MODEL_URLS[variant], model_path, getter, force=force, min_bytes=min_bytes)
    _fetch_one(VOICES_URL, voices_path, getter, force=force, min_bytes=min_bytes)
    return model_path, voices_path


def _fetch_one(url: str, dest: Path, fetch: Fetch, *, force: bool, min_bytes: int) -> None:
    if dest.is_file() and dest.stat().st_size >= min_bytes and not force:
        return
    fetch(url, dest)
    if not dest.is_file() or dest.stat().st_size < min_bytes:
        dest.unlink(missing_ok=True)
        raise AudioOverviewError(f"Download from {url} was too small to be a Kokoro file.")


def _http_download(url: str, dest: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "audio-overview/0.1"})
    temporary = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(request, timeout=180) as response, temporary.open("wb") as handle:
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise AudioOverviewError(f"Could not download {url}: {exc}") from exc
    temporary.replace(dest)
