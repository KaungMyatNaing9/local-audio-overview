"""Pack a long document into chunks on paragraph boundaries."""

from __future__ import annotations

import re

from audio_overview.errors import AudioOverviewError
from audio_overview.textutil import sentences
from audio_overview.types import Chunk

_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


def chunk_text(text: str, max_chars: int = 4000, overlap_chars: int = 200) -> list[Chunk]:
    if max_chars < 200:
        raise AudioOverviewError("chunk size must be at least 200 characters.")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise AudioOverviewError("overlap must be zero or smaller than the chunk size.")
    units = _units(text, max_chars)
    if not units:
        return []
    raw: list[str] = []
    buf: list[str] = []
    size = 0
    pending_tail = ""
    for unit in units:
        extra = len(unit) if not buf else len(unit) + 2
        if buf and size + extra > max_chars:
            raw.append("\n\n".join(buf))
            pending_tail = _tail(raw[-1], overlap_chars)
            buf = []
            size = 0
            if pending_tail:
                buf.append(pending_tail)
                size = len(pending_tail)
            extra = len(unit) if not buf else len(unit) + 2
        if buf and size + extra > max_chars:
            raw.append("\n\n".join(buf))
            buf = [unit]
            size = len(unit)
            continue
        buf.append(unit)
        size += extra
    if buf:
        raw.append("\n\n".join(buf))
    return [_make_chunk(index, piece) for index, piece in enumerate(raw)]


def _units(text: str, max_chars: int) -> list[str]:
    blocks = [block.strip() for block in re.split(r"\n\s*\n", text.strip()) if block.strip()]
    merged: list[str] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if (
            block.startswith("#")
            and _HEADING.match(block.splitlines()[0])
            and index + 1 < len(blocks)
            and not blocks[index + 1].startswith("#")
        ):
            block = block + "\n\n" + blocks[index + 1]
            index += 2
        else:
            index += 1
        merged.extend(_fit(block, max_chars))
    return merged


def _fit(block: str, max_chars: int) -> list[str]:
    if len(block) <= max_chars:
        return [block]
    pieces = sentences(block)
    if len(pieces) <= 1:
        return _hard(block, max_chars)
    out: list[str] = []
    buf = ""
    for piece in pieces:
        if len(piece) > max_chars:
            if buf:
                out.append(buf)
                buf = ""
            out.extend(_hard(piece, max_chars))
            continue
        candidate = piece if not buf else f"{buf} {piece}"
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            if buf:
                out.append(buf)
            buf = piece
    if buf:
        out.append(buf)
    return out


def _hard(text: str, max_chars: int) -> list[str]:
    words = text.split()
    if not words:
        return []
    out: list[str] = []
    buf = ""
    for word in words:
        if len(word) > max_chars:
            if buf:
                out.append(buf)
                buf = ""
            for start in range(0, len(word), max_chars):
                out.append(word[start : start + max_chars])
            continue
        candidate = word if not buf else f"{buf} {word}"
        if len(candidate) <= max_chars:
            buf = candidate
        else:
            out.append(buf)
            buf = word
    if buf:
        out.append(buf)
    return out


def _tail(text: str, overlap_chars: int) -> str:
    if overlap_chars <= 0:
        return ""
    snippet = text[-overlap_chars:].strip()
    if not snippet:
        return ""
    space = snippet.find(" ")
    if 0 <= space < len(snippet) - 1:
        snippet = snippet[space + 1 :].strip()
    return snippet


def _make_chunk(index: int, text: str) -> Chunk:
    match = _HEADING.search(text)
    heading = match.group(1).strip() if match else None
    return Chunk(index=index, text=text, heading=heading)
