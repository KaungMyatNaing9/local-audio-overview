"""Pick an ingestor from a path or URL."""

from __future__ import annotations

import re
from pathlib import Path

from audio_overview.errors import AudioOverviewError
from audio_overview.ingest.pdf import ingest_pdf
from audio_overview.ingest.repo import ingest_repo
from audio_overview.ingest.text import ingest_text
from audio_overview.ingest.web import Fetcher, ingest_url
from audio_overview.types import Document

_URL = re.compile(r"^https?://", re.IGNORECASE)


def load_source(source: str, fetcher: Fetcher | None = None) -> Document:
    if _URL.match(source):
        return ingest_url(source, fetcher=fetcher)
    path = Path(source).expanduser()
    if not path.exists():
        raise AudioOverviewError(f"Source not found: {source}")
    if path.is_dir():
        return ingest_repo(path)
    if path.suffix.lower() == ".pdf":
        return ingest_pdf(path)
    return ingest_text(path)
