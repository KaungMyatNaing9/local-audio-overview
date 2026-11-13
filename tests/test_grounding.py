from audio_overview.ingest.text import ingest_text
from audio_overview.script.grounding import check_grounding
from audio_overview.script.schema import parse_script
from audio_overview.types import ScriptLine
from tests.conftest import SAMPLE, SAMPLE_SCRIPT

HOSTS = {"Maya", "Leo"}


def _pair(first: str, second: str = "Go on.") -> tuple[ScriptLine, ScriptLine]:
    return (ScriptLine("Maya", first, "Room"), ScriptLine("Leo", second, "Room"))


def test_number_present_and_absent() -> None:
    source = "It opened in 1998 beside 18 Warder Street."
    assert check_grounding(_pair("It opened in 1998."), source, HOSTS) == ()
    flags = check_grounding(_pair("The code is 987654."), source, HOSTS)
    assert [flag.kind for flag in flags] == ["number"]
    assert flags[0].span == "987654"


def test_commas_and_percentages() -> None:
    source = "The kit is 12 percent off and costs 1,200 dollars."
    assert check_grounding(_pair("It is 12% and the price is 1200 dollars."), source, HOSTS) == ()
    flags = check_grounding(_pair("It is 44% off."), source, HOSTS)
    assert flags[0].kind == "number"
    assert "44" in flags[0].span


def test_contractions_are_not_quotations() -> None:
    line = "What's the plan for today? We're staying with the page, and I'm glad."
    assert check_grounding(_pair(line), "a quiet page", HOSTS) == ()


def test_quotations() -> None:
    source = 'The note reads: "Fourteen folds. No scissors. One minute in the water."'
    quoted = 'The note reads: "Fourteen folds. No scissors. One minute in the water."'
    assert check_grounding(_pair(quoted), source, HOSTS) == ()
    flags = check_grounding(_pair('She promised: "This boat will win the fair."'), source, HOSTS)
    assert flags[0].kind == "quotation"
    single = check_grounding(
        _pair("She said 'bring a small cup of water' and then stopped."),
        source,
        HOSTS,
    )
    assert any(flag.kind == "quotation" and "small cup" in flag.span for flag in single)


def test_names_hosts_and_the_sentence_start_gap() -> None:
    source = "Mina Voss keeps the ledger."
    assert check_grounding(_pair("The ledger belongs to Mina Voss."), source, HOSTS) == ()
    invented = check_grounding(_pair("The ledger belongs to Mina Cho."), source, HOSTS)
    assert any(flag.span == "Mina Cho" for flag in invented)
    # A name only at the start of a sentence is a known gap.
    assert check_grounding(_pair("Kokoro sits in the lab."), "a quiet lab", HOSTS) == ()
    mid = check_grounding(_pair("The lab uses Kokoro daily."), "a quiet lab", HOSTS)
    assert any(flag.span == "Kokoro" and flag.kind == "name" for flag in mid)
    assert check_grounding(_pair("Maya thinks the page is enough."), "a quiet page", HOSTS) == ()


def test_reaction_without_facts_is_not_flagged() -> None:
    lines = _pair("That's fascinating.", "Go on, I'm following.")
    assert check_grounding(lines, "Nothing about that reaction.", HOSTS) == ()


def test_bundled_sample_script_is_grounded() -> None:
    document = ingest_text(SAMPLE)
    lines = parse_script(SAMPLE_SCRIPT.read_text(encoding="utf-8"), "Maya", "Leo")
    flags = check_grounding(lines, document.text, HOSTS)
    assert flags == ()
