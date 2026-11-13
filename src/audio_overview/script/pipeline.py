"""Outline a document, write a two-host script, then check grounding."""

from __future__ import annotations

from typing import Protocol

from audio_overview.ingest.chunk import chunk_text
from audio_overview.script import prompts
from audio_overview.script.grounding import check_grounding
from audio_overview.script.schema import parse_outline, parse_points, parse_script
from audio_overview.settings import Settings
from audio_overview.types import Document, ScriptDraft

# One outline call while the source still fits a small local context.
# Longer sources are noted chunk by chunk, then merged.
SINGLE_PASS_CHARS = 14_000


class LanguageBackend(Protocol):
    name: str

    def complete(self, messages: list[dict[str, str]]) -> str: ...


def write_script(document: Document, backend: LanguageBackend, settings: Settings) -> ScriptDraft:
    chunks = chunk_text(document.text, settings.chunk_chars, settings.chunk_overlap)
    include_source = len(document.text) <= SINGLE_PASS_CHARS
    if len(chunks) > 1 and not include_source:
        notes: list[str] = []
        for chunk in chunks:
            raw = backend.complete(prompts.chunk_notes_messages(document, chunk, settings))
            notes.extend(parse_points(raw))
        outline_raw = backend.complete(prompts.merge_outline_messages(document, notes, settings))
    else:
        outline_raw = backend.complete(prompts.outline_messages(document, settings))
    outline = parse_outline(outline_raw)
    script_raw = backend.complete(
        prompts.script_messages(document, outline, settings, include_source=include_source)
    )
    lines = parse_script(script_raw, settings.host_a, settings.host_b)
    allowed = _allowed_names(settings)
    flags = check_grounding(lines, document.text, allowed)
    repaired = False
    if flags and settings.repair:
        repaired_raw = backend.complete(
            prompts.repair_messages(document, lines, flags, settings, include_source=include_source)
        )
        lines = parse_script(repaired_raw, settings.host_a, settings.host_b)
        flags = check_grounding(lines, document.text, allowed)
        repaired = True
    return ScriptDraft(
        lines=lines,
        outline=outline,
        flags=flags,
        backend=backend.name,
        repaired=repaired,
    )


def _allowed_names(settings: Settings) -> set[str]:
    names = {settings.host_a, settings.host_b}
    for host in (settings.host_a, settings.host_b):
        names.update(part for part in host.split() if part)
    return names
