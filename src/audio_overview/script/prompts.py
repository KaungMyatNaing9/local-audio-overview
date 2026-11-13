"""Prompts for the outline-then-dialogue pipeline.

Markers such as ``TASK:`` and ``SOURCE_BEGIN`` are stable: the fake backend
and the tests read them, and a real model is told to ignore them as labels.
"""

from __future__ import annotations

import json

from audio_overview.settings import Settings
from audio_overview.types import Chunk, Document, GroundingFlag, OutlineSection, ScriptLine

_TONE = {
    "conversational": (
        "Sound like two curious friends. Use contractions and short turns. "
        "Do not add jokes that depend on facts outside the source."
    ),
    "explanatory": (
        "One host explains, the other asks for the next point. Define a term only with words from the source."
    ),
    "skeptical": (
        "One host keeps the other honest. Questions are fine. "
        "Answers must quote or restate the source, and must not supply a new fact."
    ),
    "enthusiastic": (
        "Warm and energetic, still limited to the source. Do not upgrade a detail into a bigger claim."
    ),
}
_LENGTH = {
    "short": "8 to 12 turns and about 160 to 220 words.",
    "medium": "16 to 24 turns and about 450 to 650 words.",
    "long": "30 to 40 turns and about 900 to 1200 words.",
}


def chunk_notes_messages(document: Document, chunk: Chunk, settings: Settings) -> list[dict[str, str]]:
    system = (
        "TASK: chunk-notes\n\n"
        "You extract notes for an audio overview.\n"
        "Use only the chunk. Do not add names, numbers, or events.\n"
        "Reply with one JSON object and no other text."
    )
    user = (
        f"TITLE: {document.title}\n"
        f"CHUNK: {chunk.index}\n\n"
        "CHUNK_BEGIN\n"
        f"{chunk.text}\n"
        "CHUNK_END\n\n"
        'Return {"points": ["short point copied from the chunk"]}. '
        "Three to six points. Prefer sentences from the chunk."
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def outline_messages(document: Document, settings: Settings) -> list[dict[str, str]]:
    system = (
        "TASK: outline\n\n"
        "You outline a source for a two-host audio overview.\n"
        "Every point must be supported by the source. Do not add outside facts.\n"
        "Reply with one JSON object and no other text."
    )
    user = (
        _header(document, settings)
        + "\nSOURCE_BEGIN\n"
        + document.text
        + "\nSOURCE_END\n\n"
        + "Return JSON of this shape:\n"
        + '{"sections": [{"title": "section title from the source", '
        + '"points": ["point copied from the source"]}]}'
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def merge_outline_messages(document: Document, notes: list[str], settings: Settings) -> list[dict[str, str]]:
    system = (
        "TASK: outline\n\n"
        "You merge chunk notes into one outline for a two-host audio overview.\n"
        "Do not add facts that are not already in the notes.\n"
        "Reply with one JSON object and no other text."
    )
    user = (
        _header(document, settings)
        + "\nNOTES_BEGIN\n"
        + json.dumps(notes, ensure_ascii=False)
        + "\nNOTES_END\n\n"
        + "Return JSON of this shape:\n"
        + '{"sections": [{"title": "section title", "points": ["point from the notes"]}]}'
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def script_messages(
    document: Document,
    outline: tuple[OutlineSection, ...],
    settings: Settings,
    *,
    include_source: bool,
) -> list[dict[str, str]]:
    outline_payload = {
        "sections": [{"title": section.title, "points": list(section.points)} for section in outline]
    }
    source_block = (
        "SOURCE_BEGIN\n" + document.text + "\nSOURCE_END\n\n"
        if include_source
        else (
            "SOURCE: omitted because the document is long. "
            "Use only the outline points, which were taken from the source.\n\n"
        )
    )
    system = (
        "TASK: script\n\n"
        "You write a two-host audio overview grounded only in the provided source.\n"
        "Never invent a name, number, date, quotation, or event.\n"
        "If a reaction adds no new fact, it is allowed. A witty claim is not.\n"
        "Output JSON lines only. No markdown fence and no preamble.\n"
        "Each line is an object with speaker, text, and section."
    )
    user = (
        _header(document, settings)
        + "\n"
        + source_block
        + "OUTLINE_BEGIN\n"
        + json.dumps(outline_payload, ensure_ascii=False)
        + "\nOUTLINE_END\n\n"
        + f"Tone: {_TONE[settings.tone]}\n"
        + f"Length: {_LENGTH[settings.length]}\n"
        + f"Speakers must be exactly {settings.host_a} and {settings.host_b}. "
        + "Both speak. Alternate most turns.\n"
        + "Set section to an outline title so the episode can be chaptered.\n"
        + "Example line:\n"
        + json.dumps(
            {
                "speaker": settings.host_a,
                "text": "A single spoken turn.",
                "section": "Opening",
            },
            ensure_ascii=False,
        )
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def repair_messages(
    document: Document,
    lines: tuple[ScriptLine, ...],
    flags: tuple[GroundingFlag, ...],
    settings: Settings,
    *,
    include_source: bool,
) -> list[dict[str, str]]:
    problems = [
        {
            "line": flag.line_index + 1,
            "speaker": flag.speaker,
            "kind": flag.kind,
            "span": flag.span,
            "reason": flag.reason,
        }
        for flag in flags
    ]
    source_block = "SOURCE_BEGIN\n" + document.text + "\nSOURCE_END\n\n" if include_source else ""
    system = (
        "TASK: repair\n\n"
        "You rewrite a two-host script so every flagged span is removed or replaced "
        "with wording that appears in the source.\n"
        "Do not introduce new names or numbers.\n"
        "Output the full script as JSON lines only."
    )
    user = (
        _header(document, settings)
        + "\n"
        + source_block
        + "FLAGS_BEGIN\n"
        + json.dumps(problems, ensure_ascii=False)
        + "\nFLAGS_END\n\n"
        + "SCRIPT_BEGIN\n"
        + "\n".join(
            json.dumps(
                {"speaker": line.speaker, "text": line.text, "section": line.section},
                ensure_ascii=False,
            )
            for line in lines
        )
        + "\nSCRIPT_END"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _header(document: Document, settings: Settings) -> str:
    return (
        f"LENGTH: {settings.length}\n"
        f"TONE: {settings.tone}\n"
        f"HOST_A: {settings.host_a}\n"
        f"HOST_B: {settings.host_b}\n"
        f"TITLE: {document.title}"
    )
