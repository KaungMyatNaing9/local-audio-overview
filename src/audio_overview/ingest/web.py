"""Fetch a URL and keep the readable article, not the navigation chrome."""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable

import trafilatura

from audio_overview.errors import AudioOverviewError
from audio_overview.ingest.document import parse_markdown, render_document
from audio_overview.ingest.pdf import ingest_pdf_bytes
from audio_overview.types import Document, Section

Fetcher = Callable[[str], tuple[str, bytes]]
_MAX_BYTES = 8_000_000
_USER_AGENT = "audio-overview/0.1"


def article_from_html(html: str, source: str) -> Document:
    markdown = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
        output_format="markdown",
    )
    if not markdown or not markdown.strip():
        raise AudioOverviewError(f"Could not extract article text from {source}.")
    meta = trafilatura.extract_metadata(html)
    parsed_title, sections = parse_markdown(markdown)
    title = ""
    if meta is not None and meta.title:
        title = str(meta.title).strip()
    title = title or parsed_title or "Untitled article"
    if not sections:
        sections = [Section("Overview", markdown.strip(), 2)]
    return Document(
        title=title,
        text=render_document(title, sections),
        source=source,
        kind="url",
        sections=tuple(sections),
    )


def ingest_url(url: str, fetcher: Fetcher | None = None, timeout: float = 30.0) -> Document:
    if not url.startswith(("http://", "https://")):
        raise AudioOverviewError(f"Not an http(s) URL: {url}")
    content_type, payload = (fetcher or _default_fetcher(timeout))(url)
    if not payload:
        raise AudioOverviewError(f"Empty response from {url}.")
    kind = content_type.lower()
    if "pdf" in kind or url.lower().split("?", 1)[0].endswith(".pdf"):
        return ingest_pdf_bytes(payload, source=url)
    try:
        html = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise AudioOverviewError(f"{url} is not UTF-8 HTML or a PDF.") from exc
    return article_from_html(html, url)


def _default_fetcher(timeout: float) -> Fetcher:
    def fetch(url: str) -> tuple[str, bytes]:
        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                payload = response.read(_MAX_BYTES + 1)
        except urllib.error.URLError as exc:
            raise AudioOverviewError(f"Could not fetch {url}: {exc.reason}") from exc
        if len(payload) > _MAX_BYTES:
            raise AudioOverviewError(f"{url} is larger than 8MB. V1 refuses it.")
        return content_type, payload

    return fetch
