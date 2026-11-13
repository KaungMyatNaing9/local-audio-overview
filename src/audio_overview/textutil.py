"""Small text helpers shared by ingestion, the fake script, and speech."""

from __future__ import annotations

import re

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[\"'“A-Z0-9])")
_FENCE = re.compile(r"^```[a-zA-Z0-9_-]*\s*|\s*```$")


def sentences(text: str) -> list[str]:
    """Split prose on sentence boundaries.

    A block with no terminator is returned as one sentence. Periods inside
    numbers (``3.5``) are kept because a split requires following whitespace.
    """

    found: list[str] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        flat = " ".join(block.split())
        if not flat:
            continue
        parts = [part.strip() for part in _SENTENCE_SPLIT.split(flat) if part.strip()]
        found.extend(parts or [flat])
    return found


def strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = _FENCE.sub("", text).strip()
    return text


def collapse(text: str) -> str:
    text = text.lower().replace("’", "'").replace("‘", "'")
    text = text.replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip()
