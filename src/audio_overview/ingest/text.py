"""Load a local markdown or plain-text file."""

from __future__ import annotations

from pathlib import Path

from audio_overview.errors import AudioOverviewError
from audio_overview.ingest.document import looks_like_markdown, parse_markdown, render_document
from audio_overview.types import Document, Section

_MARKDOWN_SUFFIXES = {".md", ".markdown", ".mdown"}


def ingest_text(path: Path) -> Document:
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AudioOverviewError(
            f"{path} is not UTF-8 text. V1 reads UTF-8 markdown and text files."
        ) from exc
    if not raw.strip():
        raise AudioOverviewError(f"No text in {path}.")
    as_markdown = path.suffix.lower() in _MARKDOWN_SUFFIXES or looks_like_markdown(raw)
    if as_markdown:
        title, sections = parse_markdown(raw)
        title = title or _title_from_name(path)
        kind = "markdown"
    else:
        title = _title_from_name(path)
        sections = [Section("Overview", raw.strip(), 2)]
        kind = "text"
    if not sections:
        raise AudioOverviewError(f"No body text in {path}.")
    return Document(
        title=title,
        text=render_document(title, sections),
        source=str(path),
        kind=kind,
        sections=tuple(sections),
    )


def _title_from_name(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").strip() or path.name
