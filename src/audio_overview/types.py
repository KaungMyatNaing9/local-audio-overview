"""Shared records for a document, its script, and the spoken episode."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Section:
    heading: str
    text: str
    level: int = 2


@dataclass(frozen=True)
class Document:
    """Text the script is allowed to use.

    ``text`` is the grounding source. For a git repo it is the summary we
    built (README, tree, and excerpts), not every unread file.
    """

    title: str
    text: str
    source: str
    kind: str
    sections: tuple[Section, ...] = ()
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def word_count(self) -> int:
        return len(self.text.split())


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    heading: str | None = None


@dataclass(frozen=True)
class ScriptLine:
    speaker: str
    text: str
    section: str | None = None


@dataclass(frozen=True)
class GroundingFlag:
    line_index: int
    speaker: str
    text: str
    span: str
    kind: str
    reason: str


@dataclass(frozen=True)
class OutlineSection:
    title: str
    points: tuple[str, ...]


@dataclass(frozen=True)
class ScriptDraft:
    lines: tuple[ScriptLine, ...]
    outline: tuple[OutlineSection, ...]
    flags: tuple[GroundingFlag, ...]
    backend: str
    repaired: bool


@dataclass(frozen=True)
class TimedLine:
    line: ScriptLine
    start_ms: int
    duration_ms: int


@dataclass(frozen=True)
class Chapter:
    title: str
    start_ms: int
    end_ms: int
