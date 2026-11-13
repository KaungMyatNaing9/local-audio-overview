"""A deterministic backend for tests and for machines with no language model.

Without a replay file it does not paraphrase. The hosts read sentences from
the source, in order, so the grounding check has nothing new to catch.
"""

from __future__ import annotations

import json
import re

from audio_overview.errors import AudioOverviewError
from audio_overview.textutil import sentences
from audio_overview.types import Document, ScriptLine

_TASK = re.compile(r"^TASK:\s*(\S+)\s*$", re.MULTILINE)
_FIELD = re.compile(r"^(LENGTH|TONE|HOST_A|HOST_B):\s*(.+)\s*$", re.MULTILINE)
_CHUNK = re.compile(r"CHUNK_BEGIN\n(.*?)\nCHUNK_END", re.DOTALL)
_CAPS = {"short": 6, "medium": 14, "long": 28}
_TONE_LINE = {
    "conversational": "Let's stay with what the page actually says.",
    "explanatory": "We will go in order and keep each point tied to the text.",
    "skeptical": "I only want what the text itself says.",
    "enthusiastic": "We will take the page in order, and we will not add to it.",
}


class FakeBackend:
    """Replay a script, or build a grounded read-through from the document."""

    name = "fake"

    def __init__(self, document: Document, replay: tuple[ScriptLine, ...] | None = None) -> None:
        self.document = document
        self.replay = replay
        self.tasks: list[str] = []

    def complete(self, messages: list[dict[str, str]]) -> str:
        task = task_name(messages)
        self.tasks.append(task)
        if task == "chunk-notes":
            return _chunk_notes(messages)
        if task == "outline":
            return _outline(self.document)
        if task in {"script", "repair"}:
            if self.replay is not None:
                return _jsonl(self.replay)
            return _jsonl(read_through(self.document, _options(messages)))
        raise AudioOverviewError(f"Unknown model task {task!r}.")


def task_name(messages: list[dict[str, str]]) -> str:
    for message in messages:
        match = _TASK.search(message.get("content", ""))
        if match:
            return match.group(1)
    raise AudioOverviewError("A model prompt is missing its TASK line.")


def read_through(document: Document, options: dict[str, str]) -> tuple[ScriptLine, ...]:
    host_a = options.get("HOST_A") or "Maya"
    host_b = options.get("HOST_B") or "Leo"
    tone = options.get("TONE") or "conversational"
    length = options.get("LENGTH") or "short"
    cap = _CAPS.get(length, _CAPS["short"])
    spoken = _TONE_LINE.get(tone, _TONE_LINE["conversational"])
    rows: list[tuple[str, str]] = []
    for section in document.sections:
        for sentence in sentences(section.text):
            rows.append((section.heading, sentence))
    chosen = rows[:cap]
    lines = [
        ScriptLine(host_a, f"This overview follows {document.title}.", "Opening"),
        ScriptLine(host_b, spoken, "Opening"),
    ]
    speakers = (host_a, host_b)
    for index, (heading, sentence) in enumerate(chosen):
        lines.append(ScriptLine(speakers[index % 2], sentence, heading))
    closing = chosen[-1][0] if chosen else "Opening"
    lines.append(ScriptLine(speakers[len(chosen) % 2], "That is the end of the source.", closing))
    if lines[-1].speaker == lines[-2].speaker:
        other = host_b if lines[-1].speaker == host_a else host_a
        lines[-1] = ScriptLine(other, lines[-1].text, lines[-1].section)
    return tuple(lines)


def _options(messages: list[dict[str, str]]) -> dict[str, str]:
    blob = "\n".join(message.get("content", "") for message in messages)
    return {match.group(1): match.group(2).strip() for match in _FIELD.finditer(blob)}


def _chunk_notes(messages: list[dict[str, str]]) -> str:
    blob = "\n".join(message.get("content", "") for message in messages)
    match = _CHUNK.search(blob)
    text = match.group(1) if match else ""
    points = sentences(text)[:3]
    return json.dumps({"points": points}, ensure_ascii=False)


def _outline(document: Document) -> str:
    sections = []
    for section in document.sections[:8]:
        points = sentences(section.text)[:2]
        sections.append({"title": section.heading, "points": points})
    if not sections:
        sections.append({"title": document.title, "points": sentences(document.text)[:4]})
    return json.dumps({"sections": sections}, ensure_ascii=False)


def _jsonl(lines: tuple[ScriptLine, ...]) -> str:
    rows = []
    for line in lines:
        payload: dict[str, str] = {"speaker": line.speaker, "text": line.text}
        if line.section:
            payload["section"] = line.section
        rows.append(json.dumps(payload, ensure_ascii=False))
    return "\n".join(rows)
