import json

import pytest

from audio_overview.errors import ScriptSchemaError
from audio_overview.script.schema import parse_outline, parse_script


def test_jsonl_and_array_and_fence() -> None:
    jsonl = (
        '{"speaker": "maya", "text": "The basin is stone.", "section": "Room"}\n'
        '{"speaker": "LEO", "text": "It opened in 1998."}\n'
    )
    lines = parse_script(jsonl, "Maya", "Leo")
    assert [line.speaker for line in lines] == ["Maya", "Leo"]
    assert lines[0].section == "Room"
    array = json.dumps(
        [
            {"speaker": "Maya", "text": "One."},
            {"speaker": "Leo", "text": "Two."},
        ]
    )
    assert len(parse_script(array, "Maya", "Leo")) == 2
    fenced = "```json\n" + jsonl + "```"
    assert len(parse_script(fenced, "Maya", "Leo")) == 2


def test_wrapped_lines_object() -> None:
    raw = json.dumps({"lines": [{"speaker": "Maya", "text": "One."}, {"speaker": "Leo", "text": "Two."}]})
    assert len(parse_script(raw, "Maya", "Leo")) == 2


def test_schema_rejects_bad_scripts() -> None:
    with pytest.raises(ScriptSchemaError, match="only allows"):
        parse_script(
            '{"speaker": "Sam", "text": "Hello."}\n{"speaker": "Maya", "text": "Hi."}\n',
            "Maya",
            "Leo",
        )
    with pytest.raises(ScriptSchemaError, match="empty"):
        parse_script(
            '{"speaker": "Maya", "text": "   "}\n{"speaker": "Leo", "text": "Hi."}\n',
            "Maya",
            "Leo",
        )
    with pytest.raises(ScriptSchemaError, match="Both"):
        parse_script(
            '{"speaker": "Maya", "text": "One."}\n{"speaker": "Maya", "text": "Two."}\n',
            "Maya",
            "Leo",
        )
    with pytest.raises(ScriptSchemaError, match="at least two"):
        parse_script('{"speaker": "Maya", "text": "Only one."}\n', "Maya", "Leo")


def test_outline_requires_sections() -> None:
    outline = parse_outline('{"sections": [{"title": "Room", "points": ["The door is green."]}]}')
    assert outline[0].title == "Room"
    assert outline[0].points == ("The door is green.",)
    with pytest.raises(ScriptSchemaError):
        parse_outline("not json")
