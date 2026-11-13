import json

from audio_overview.script.fake import FakeBackend
from audio_overview.script.pipeline import write_script
from audio_overview.script.prompts import outline_messages, script_messages
from audio_overview.settings import Settings
from audio_overview.types import Document, OutlineSection, Section


def _document() -> Document:
    sections = (
        Section("The room", "The door is painted a dull green. It opened in 1998.", 2),
        Section("The class", "Mina Voss teaches nine people. A finished skiff takes 14 folds.", 2),
        Section(
            "The basin",
            "The basin is fed by a rain barrel. Six boats earned the mark. "
            "The class lasts 70 minutes. The first quiet stretch is 20 minutes. "
            "A kit costs 12 dollars. The ledger is a gray notebook.",
            2,
        ),
    )
    text = "# Paper boats\n\n" + "\n\n".join(
        f"## {section.heading}\n\n{section.text}" for section in sections
    )
    return Document("Paper boats", text, "memory", "markdown", sections)


def test_fake_read_through_is_grounded_and_scales_with_length() -> None:
    document = _document()
    short = write_script(document, FakeBackend(document), Settings(length="short", repair=True))
    long = write_script(document, FakeBackend(document), Settings(length="long", repair=True))
    assert short.flags == ()
    assert long.flags == ()
    assert len(short.lines) < len(long.lines)
    assert {line.speaker for line in short.lines} == {"Maya", "Leo"}
    assert short.backend == "fake"
    assert "1998" in " ".join(line.text for line in short.lines)


def test_long_source_asks_for_chunk_notes() -> None:
    body = " ".join(
        f"The cedar note {index:04d} records a quiet fold in the basin." for index in range(1, 280)
    )
    text = f"# Cedar Notes\n\n## Notes\n\n{body}\n"
    document = Document("Cedar Notes", text, "memory", "markdown", (Section("Notes", body, 2),))
    backend = FakeBackend(document)
    draft = write_script(
        document,
        backend,
        Settings(length="short", chunk_chars=1500, chunk_overlap=40, repair=True),
    )
    assert "chunk-notes" in backend.tasks
    assert draft.flags == ()


def test_short_source_does_not_need_chunk_notes() -> None:
    document = _document()
    backend = FakeBackend(document)
    write_script(document, backend, Settings(length="short"))
    assert backend.tasks == ["outline", "script"]


def test_prompts_carry_the_source_and_the_task() -> None:
    document = _document()
    settings = Settings()
    outline = outline_messages(document, settings)
    assert "TASK: outline" in outline[0]["content"]
    assert "SOURCE_BEGIN" in outline[1]["content"]
    assert "1998" in outline[1]["content"]
    assert "HOST_A: Maya" in outline[1]["content"]
    script = script_messages(
        document,
        (OutlineSection("The room", ("The door is painted a dull green.",)),),
        settings,
        include_source=True,
    )
    assert "TASK: script" in script[0]["content"]
    assert "Maya" in script[1]["content"]
    assert "Leo" in script[1]["content"]
    assert settings.tone in script[1]["content"]


class _Sequence:
    name = "sequence"

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.calls = 0

    def complete(self, messages: list[dict[str, str]]) -> str:
        reply = self.replies[self.calls]
        self.calls += 1
        return reply


def test_repair_pass_replaces_an_ungrounded_number() -> None:
    document = _document()
    outline = json.dumps({"sections": [{"title": "The room", "points": ["It opened in 1998."]}]})
    bad = (
        '{"speaker": "Maya", "text": "The code is 55555.", "section": "The room"}\n'
        '{"speaker": "Leo", "text": "It opened in 1998.", "section": "The room"}\n'
    )
    fixed = (
        '{"speaker": "Maya", "text": "It opened in 1998.", "section": "The room"}\n'
        '{"speaker": "Leo", "text": "I am following the page.", "section": "The room"}\n'
    )
    backend = _Sequence([outline, bad, fixed])
    draft = write_script(document, backend, Settings(repair=True))
    assert backend.calls == 3
    assert draft.repaired is True
    assert draft.flags == ()


def test_replay_is_what_the_fake_backend_speaks() -> None:
    document = _document()
    replay = (
        '{"speaker": "Maya", "text": "It opened in 1998.", "section": "The room"}\n'
        '{"speaker": "Leo", "text": "The door is painted a dull green.", "section": "The room"}\n'
    )
    from audio_overview.script.schema import parse_script

    lines = parse_script(replay, "Maya", "Leo")
    draft = write_script(document, FakeBackend(document, replay=lines), Settings(repair=False))
    assert draft.lines == lines
