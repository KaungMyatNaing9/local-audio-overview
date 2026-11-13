"""Turn sections into the single text block used for grounding."""

from __future__ import annotations

import re

from audio_overview.types import Section

_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def parse_markdown(text: str) -> tuple[str | None, list[Section]]:
    """Split CommonMark ATX headings. Fenced code is not treated as headings."""

    title: str | None = None
    sections: list[Section] = []
    heading: str | None = None
    level = 2
    buf: list[str] = []
    in_fence = False

    def flush() -> None:
        nonlocal buf
        body = "\n".join(buf).strip()
        buf = []
        if not body:
            return
        sections.append(Section(heading or "Overview", body, level if heading else 2))

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            buf.append(line)
            continue
        if not in_fence:
            match = _HEADING.match(line)
            if match:
                hashes, label = match.group(1), match.group(2).strip()
                if len(hashes) == 1 and title is None:
                    flush()
                    title = label
                    heading = None
                    continue
                flush()
                heading = label
                level = len(hashes)
                continue
        buf.append(line)
    flush()
    return title, sections


def render_document(title: str, sections: list[Section] | tuple[Section, ...]) -> str:
    parts = [f"# {title.strip() or 'Untitled'}"]
    for section in sections:
        level = min(6, max(2, section.level))
        heading = section.heading.strip() or "Overview"
        body = section.text.strip()
        parts.append(f"{'#' * level} {heading}\n\n{body}")
    return "\n\n".join(parts).strip() + "\n"


def looks_like_markdown(text: str) -> bool:
    hits = 0
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and _HEADING.match(line):
            hits += 1
            if hits >= 1 and line.startswith("# "):
                return True
    return hits >= 2
