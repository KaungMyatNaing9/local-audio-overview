"""Transcript, chapter list, and the grounding report written beside the audio."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from audio_overview.script.schema import script_to_jsonl
from audio_overview.settings import Settings
from audio_overview.types import Chapter, Document, ScriptDraft, TimedLine


def sidecar(output: Path, suffix: str) -> Path:
    return output.with_name(output.stem + suffix)


def format_clock(ms: int) -> str:
    seconds = max(0, ms) // 1000
    return f"{seconds // 60}:{seconds % 60:02d}"


def format_duration(ms: int) -> str:
    total = max(0, ms) // 1000
    minutes, seconds = divmod(total, 60)
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def write_sidecars(
    output: Path,
    document: Document,
    draft: ScriptDraft,
    settings: Settings,
    timed: Sequence[TimedLine] | None,
    chapters: Sequence[Chapter] | None,
    duration_ms: int | None,
) -> dict[str, Path]:
    script_path = sidecar(output, ".script.jsonl")
    grounding_path = sidecar(output, ".grounding.json")
    script_path.write_text(script_to_jsonl(draft.lines) + "\n", encoding="utf-8")
    grounding_path.write_text(_grounding_json(draft), encoding="utf-8")
    paths = {"script": script_path, "grounding": grounding_path}
    if timed is None or chapters is None or duration_ms is None:
        return paths
    transcript_path = sidecar(output, ".transcript.md")
    chapters_path = sidecar(output, ".chapters.json")
    transcript_path.write_text(
        render_transcript(document, draft, settings, timed, duration_ms),
        encoding="utf-8",
    )
    chapters_path.write_text(_chapters_json(document, chapters, duration_ms), encoding="utf-8")
    paths["transcript"] = transcript_path
    paths["chapters"] = chapters_path
    return paths


def render_transcript(
    document: Document,
    draft: ScriptDraft,
    settings: Settings,
    timed: Sequence[TimedLine],
    duration_ms: int,
) -> str:
    flag_count = len({flag.line_index for flag in draft.flags})
    lines = [
        f"# {document.title}",
        "",
        f"- Source: {document.source} ({document.kind}, {document.word_count} words)",
        f"- Hosts: {settings.host_a} ({settings.voice_a}), {settings.host_b} ({settings.voice_b})",
        f"- Length: {settings.length}",
        f"- Tone: {settings.tone}",
        f"- Backend: {draft.backend}",
        f"- Duration: {format_duration(duration_ms)}",
        f"- Grounding flags: {flag_count}",
        "",
        "The grounding check looks for numbers, quotations, and proper names that",
        "are not in the source. It does not prove that a paraphrase is entailed.",
        "",
    ]
    current = None
    for item in timed:
        section = item.line.section or "Overview"
        if section != current:
            lines.append(f"## {section}")
            lines.append("")
            current = section
        lines.append(f"**[{format_clock(item.start_ms)}] {item.line.speaker}:** {item.line.text}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _grounding_json(draft: ScriptDraft) -> str:
    payload = {
        "method": "lexical",
        "checked": ["numbers", "quotations", "proper_names"],
        "not_checked": (
            "A line with no number, quotation, or proper name is not flagged, "
            "so a paraphrase can still add a claim this check will miss. "
            "A name that is only the first word of a sentence is also not flagged."
        ),
        "backend": draft.backend,
        "repaired": draft.repaired,
        "line_count": len(draft.lines),
        "flag_count": len(draft.flags),
        "flagged_lines": len({flag.line_index for flag in draft.flags}),
        "flags": [
            {
                "line": flag.line_index + 1,
                "speaker": flag.speaker,
                "kind": flag.kind,
                "span": flag.span,
                "reason": flag.reason,
                "text": flag.text,
            }
            for flag in draft.flags
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _chapters_json(document: Document, chapters: Sequence[Chapter], duration_ms: int) -> str:
    payload = {
        "title": document.title,
        "duration_ms": duration_ms,
        "chapters": [
            {"title": chapter.title, "start_ms": chapter.start_ms, "end_ms": chapter.end_ms}
            for chapter in chapters
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
