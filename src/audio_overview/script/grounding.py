"""Flag script lines whose checkable facts are not in the source.

This is a lexical check, not a proof that a paraphrase is entailed by the
source. It flags:

* digits, money amounts, and percentages that do not occur in the source
* quotations that are not substrings of the source
* proper names: a multi-word capitalized phrase anywhere, a single capitalized
  word in the middle of a sentence, or an acronym

It does not flag a name that is only the first word of a sentence, and it
does not flag ordinary wording that adds no number, quotation, or name.
Host names are allowed even when the source never mentions the hosts.
"""

from __future__ import annotations

import re

from audio_overview.textutil import collapse
from audio_overview.types import GroundingFlag, ScriptLine

_FUNCTION_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "but",
        "or",
        "nor",
        "if",
        "we",
        "i",
        "it",
        "they",
        "he",
        "she",
        "you",
        "this",
        "that",
        "these",
        "those",
        "there",
        "here",
        "when",
        "while",
        "what",
        "why",
        "how",
        "so",
        "because",
        "today",
        "now",
        "then",
        "first",
        "second",
        "next",
        "last",
        "well",
        "yes",
        "no",
        "okay",
        "ok",
        "right",
        "let",
        "please",
        "thanks",
        "hello",
        "hi",
        "welcome",
        "also",
        "still",
        "just",
        "maybe",
        "for",
        "on",
        "in",
        "at",
        "of",
        "to",
        "from",
        "with",
        "after",
        "before",
        "during",
        "its",
        "our",
        "their",
        "his",
        "her",
        "my",
        "your",
    }
)
_ACRONYM_SKIP = frozenset({"OK"})
# A trailing sentence period is not part of the number. ``3.5`` still counts as one token
# because the optional decimal group consumes a dot only when digits follow it.
_NUMBER = re.compile(
    r"(?<![\w.])(?:[$£€]\s*)?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?"
    r"|(?<![\w.])(?:[$£€]\s*)?\d+(?:\.\d+)?%?(?!\w)"
)
# Single quotes only count when they are not apostrophes inside a word, so
# "what's" and "we're" are not treated as quotations.
_QUOTE = re.compile(r"[\"“]([^\"”]{8,400})[\"”]|(?<![\w])'([^'\n]{12,400})'(?![\w])")
_NAME = re.compile(r"\b(?:[A-Z][a-z]+|[A-Z]{2,})(?:\s+(?:[A-Z][a-z]+|[A-Z]{2,}))*\b")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def check_grounding(
    lines: tuple[ScriptLine, ...] | list[ScriptLine],
    source_text: str,
    allowed_names: set[str] | None = None,
) -> tuple[GroundingFlag, ...]:
    blob = collapse(source_text)
    digits = re.sub(r"(?<=\d),(?=\d)", "", blob)
    allowed_spans = {collapse(name) for name in (allowed_names or set()) if name.strip()}
    allowed_tokens = {token for name in allowed_spans for token in name.split()}
    flags: list[GroundingFlag] = []
    for index, line in enumerate(lines):
        flags.extend(_numbers(index, line, digits))
        flags.extend(_quotes(index, line, blob))
        flags.extend(_names(index, line, blob, allowed_spans, allowed_tokens))
    return tuple(flags)


def format_flag_report(flags: tuple[GroundingFlag, ...] | list[GroundingFlag]) -> str:
    lines = [f"grounding: {len({flag.line_index for flag in flags})} lines flagged"]
    for flag in flags:
        lines.append(f"  line {flag.line_index + 1} ({flag.speaker}): {flag.reason}: {flag.span!r}")
    return "\n".join(lines)


def _numbers(index: int, line: ScriptLine, digits: str) -> list[GroundingFlag]:
    flags: list[GroundingFlag] = []
    seen: set[str] = set()
    for match in _NUMBER.finditer(line.text):
        token = match.group(0).strip()
        if token in seen:
            continue
        seen.add(token)
        if _number_supported(token, digits):
            continue
        flags.append(
            GroundingFlag(
                line_index=index,
                speaker=line.speaker,
                text=line.text,
                span=token,
                kind="number",
                reason="number not in source",
            )
        )
    return flags


def _quotes(index: int, line: ScriptLine, blob: str) -> list[GroundingFlag]:
    flags: list[GroundingFlag] = []
    for match in _QUOTE.finditer(line.text):
        inner = match.group(1) or match.group(2) or ""
        inner = inner.strip()
        if collapse(inner) in blob:
            continue
        flags.append(
            GroundingFlag(
                line_index=index,
                speaker=line.speaker,
                text=line.text,
                span=inner,
                kind="quotation",
                reason="quotation not in source",
            )
        )
    return flags


def _names(
    index: int,
    line: ScriptLine,
    blob: str,
    allowed_spans: set[str],
    allowed_tokens: set[str],
) -> list[GroundingFlag]:
    flags: list[GroundingFlag] = []
    seen: set[str] = set()
    for sentence in _SENTENCE.split(line.text.strip()):
        for match in _NAME.finditer(sentence):
            span = match.group(0)
            if span in seen:
                continue
            at_start = match.start() == 0
            tokens = span.split()
            initial = len(tokens) == 1 and at_start and tokens[0] not in _ACRONYM_SKIP
            if initial and (not tokens[0].isupper() or len(tokens[0]) < 2):
                continue
            if len(tokens) == 1 and tokens[0].lower() in _FUNCTION_WORDS:
                continue
            if span in _ACRONYM_SKIP:
                continue
            if _allowed(span, allowed_spans, allowed_tokens):
                continue
            if _name_in_source(span, blob):
                continue
            seen.add(span)
            flags.append(
                GroundingFlag(
                    line_index=index,
                    speaker=line.speaker,
                    text=line.text,
                    span=span,
                    kind="name",
                    reason="name not in source",
                )
            )
    return flags


def _allowed(span: str, allowed_spans: set[str], allowed_tokens: set[str]) -> bool:
    folded = collapse(span)
    if folded in allowed_spans:
        return True
    tokens = folded.split()
    return bool(tokens) and all(token in allowed_tokens for token in tokens)


def _name_in_source(span: str, blob: str) -> bool:
    if collapse(span) in blob:
        return True
    tokens = span.split()
    while tokens and tokens[0].lower() in _FUNCTION_WORDS:
        tokens = tokens[1:]
    while tokens and tokens[-1].lower() in _FUNCTION_WORDS:
        tokens = tokens[:-1]
    if not tokens:
        return True
    return collapse(" ".join(tokens)) in blob


def _number_supported(token: str, digits: str) -> bool:
    for form in _number_forms(token):
        if form.endswith(" percent") or form.endswith(" per cent"):
            if form in digits:
                return True
            continue
        if re.search(r"(?<!\d)" + re.escape(form) + r"(?!\d)", digits):
            return True
    return False


def _number_forms(token: str) -> list[str]:
    raw = re.sub(r"\s+", "", token.lower())
    forms: list[str] = []

    def add(value: str) -> None:
        if value and value not in forms:
            forms.append(value)

    add(raw)
    plain = raw.replace(",", "")
    add(plain)
    for prefix in ("$", "£", "€"):
        if plain.startswith(prefix):
            plain = plain[len(prefix) :]
            add(plain)
    if plain.endswith("%"):
        number = plain[:-1]
        add(number)
        add(f"{number} percent")
        add(f"{number} per cent")
    return forms
