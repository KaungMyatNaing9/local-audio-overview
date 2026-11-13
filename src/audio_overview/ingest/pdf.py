"""Extract text from a PDF. Scanned pages without a text layer are refused."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from audio_overview.errors import AudioOverviewError
from audio_overview.ingest.document import render_document
from audio_overview.types import Document, Section


def ingest_pdf(path: Path) -> Document:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise AudioOverviewError(f"Could not read {path}: {exc}") from exc
    return ingest_pdf_bytes(data, source=str(path))


def ingest_pdf_bytes(data: bytes, source: str) -> Document:
    try:
        reader = PdfReader(BytesIO(data))
    except PdfReadError as exc:
        raise AudioOverviewError(f"Could not read PDF {source}: {exc}") from exc
    sections: list[Section] = []
    for index, page in enumerate(reader.pages, start=1):
        extracted = page.extract_text() or ""
        body = extracted.strip()
        if body:
            sections.append(Section(f"Page {index}", body, 2))
    if not sections:
        raise AudioOverviewError(f"No extractable text in {source}. V1 does not OCR scanned pages.")
    title = _pdf_title(reader) or sections[0].text.splitlines()[0].strip()[:120]
    return Document(
        title=title,
        text=render_document(title, sections),
        source=source,
        kind="pdf",
        sections=tuple(sections),
        metadata={"pages": str(len(reader.pages)), "text_pages": str(len(sections))},
    )


def _pdf_title(reader: PdfReader) -> str:
    meta = reader.metadata
    if meta is None or not meta.title:
        return ""
    return str(meta.title).strip()
