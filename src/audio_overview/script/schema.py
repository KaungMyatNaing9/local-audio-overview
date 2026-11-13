"""Parse and check a two-host script."""

from __future__ import annotations

import json
from collections.abc import Iterable

from audio_overview.errors import ScriptSchemaError
from audio_overview.textutil import strip_fences
from audio_overview.types import OutlineSection, ScriptLine

_MAX_LINE = 2000


def parse_script(raw: str, host_a: str, host_b: str) -> tuple[ScriptLine, ...]:
    items = _objects(raw)
    hosts = {host_a.lower(): host_a, host_b.lower(): host_b}
    lines: list[ScriptLine] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            raise ScriptSchemaError(f"Script item {index} is not an object.")
        speaker = item.get("speaker")
        text = item.get("text")
        if not isinstance(speaker, str) or not isinstance(text, str):
            raise ScriptSchemaError(f"Script item {index} needs string speaker and text fields.")
        canonical = hosts.get(speaker.strip().lower())
        if canonical is None:
            raise ScriptSchemaError(
                f"Script item {index} uses speaker {speaker!r}. V1 only allows {host_a!r} and {host_b!r}."
            )
        body = " ".join(text.split())
        if not body:
            raise ScriptSchemaError(f"Script item {index} has empty text.")
        if len(body) > _MAX_LINE:
            raise ScriptSchemaError(
                f"Script item {index} is {len(body)} characters. Split it under {_MAX_LINE}."
            )
        section = item.get("section")
        if section is not None and not isinstance(section, str):
            raise ScriptSchemaError(f"Script item {index} has a non-string section.")
        lines.append(ScriptLine(canonical, body, section.strip() if isinstance(section, str) else None))
    if len(lines) < 2:
        raise ScriptSchemaError("A script needs at least two lines.")
    used = {line.speaker for line in lines}
    if host_a not in used or host_b not in used:
        raise ScriptSchemaError(f"Both {host_a} and {host_b} have to speak.")
    return tuple(lines)


def parse_outline(raw: str) -> tuple[OutlineSection, ...]:
    text = strip_fences(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ScriptSchemaError(f"Outline is not JSON: {text[:180]}") from exc
    sections = data.get("sections") if isinstance(data, dict) else data
    if not isinstance(sections, list) or not sections:
        raise ScriptSchemaError("Outline JSON needs a non-empty sections list.")
    parsed: list[OutlineSection] = []
    for index, item in enumerate(sections, start=1):
        if not isinstance(item, dict):
            raise ScriptSchemaError(f"Outline section {index} is not an object.")
        title = item.get("title")
        points = item.get("points", [])
        if not isinstance(title, str) or not title.strip():
            raise ScriptSchemaError(f"Outline section {index} needs a title.")
        if not isinstance(points, list):
            raise ScriptSchemaError(f"Outline section {index} points must be a list.")
        clean = tuple(str(point).strip() for point in points if str(point).strip())
        parsed.append(OutlineSection(title.strip(), clean))
    return tuple(parsed)


def parse_points(raw: str) -> tuple[str, ...]:
    text = strip_fences(raw)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ScriptSchemaError(f"Chunk notes are not JSON: {text[:180]}") from exc
    points = data.get("points") if isinstance(data, dict) else data
    if not isinstance(points, list):
        raise ScriptSchemaError("Chunk notes need a points list.")
    return tuple(str(point).strip() for point in points if str(point).strip())


def script_to_jsonl(lines: Iterable[ScriptLine]) -> str:
    rows = []
    for line in lines:
        payload: dict[str, str] = {"speaker": line.speaker, "text": line.text}
        if line.section:
            payload["section"] = line.section
        rows.append(json.dumps(payload, ensure_ascii=False))
    return "\n".join(rows)


def _objects(raw: str) -> list[object]:
    text = strip_fences(raw)
    if not text:
        raise ScriptSchemaError("The script is empty.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict) and isinstance(data.get("lines"), list):
        return list(data["lines"])
    if isinstance(data, list):
        return list(data)
    if isinstance(data, dict) and "speaker" in data:
        return [data]
    objects: list[object] = []
    started = False
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("```"):
            continue
        if not stripped.startswith("{"):
            if started:
                raise ScriptSchemaError(f"Line {line_no} is not a JSON object: {stripped[:120]}")
            continue
        try:
            objects.append(json.loads(stripped))
        except json.JSONDecodeError as exc:
            raise ScriptSchemaError(f"Line {line_no} is not valid JSON: {exc}") from exc
        started = True
    if not objects:
        raise ScriptSchemaError("No script lines found. Expected JSON lines of speaker and text.")
    return objects
