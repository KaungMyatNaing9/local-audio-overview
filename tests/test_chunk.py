from audio_overview.ingest.chunk import chunk_text


def test_short_text_is_one_chunk() -> None:
    chunks = chunk_text("The basin is stone.\n\nIt is fed by rain.", max_chars=500, overlap_chars=40)
    assert len(chunks) == 1
    assert "stone" in chunks[0].text


def test_empty_text_has_no_chunks() -> None:
    assert chunk_text("  \n", max_chars=400, overlap_chars=20) == []


def test_long_text_stays_within_the_budget_and_overlaps() -> None:
    paragraphs = [f"Paragraph {index} " + ("cedar " * 40) + f"marker{index}." for index in range(12)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, max_chars=280, overlap_chars=50)
    assert len(chunks) > 2
    assert all(len(chunk.text) <= 280 for chunk in chunks)
    shared = False
    for previous, nxt in zip(chunks, chunks[1:], strict=False):
        probe = previous.text[-40:].strip()
        if probe and probe[-20:] in nxt.text:
            shared = True
    assert shared


def test_a_huge_token_is_split() -> None:
    chunks = chunk_text("x" * 500, max_chars=200, overlap_chars=0)
    assert len(chunks) >= 3
    assert all(len(chunk.text) <= 200 for chunk in chunks)
    assert "".join(chunk.text for chunk in chunks) == "x" * 500


def test_heading_is_recorded() -> None:
    text = "# Title\n\n## Alpha\n\nThe basin is quiet.\n\n## Beta\n\nThe barrel is full."
    chunks = chunk_text(text, max_chars=2000, overlap_chars=0)
    headings = [chunk.heading for chunk in chunks]
    assert "Title" in headings or "Alpha" in headings
