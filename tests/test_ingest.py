from pathlib import Path

import pytest
from pypdf import PdfWriter

from audio_overview.errors import AudioOverviewError
from audio_overview.ingest.load import load_source
from audio_overview.ingest.text import ingest_text
from audio_overview.ingest.web import article_from_html, ingest_url
from tests.conftest import FIXTURES
from tests.pdfutil import build_pdf


def test_markdown_keeps_headings_and_title(tmp_path: Path) -> None:
    path = tmp_path / "notes.md"
    path.write_text("# Cedar Basin\n\n## April count\n\nSix boats stayed up.\n", encoding="utf-8")
    document = ingest_text(path)
    assert document.kind == "markdown"
    assert document.title == "Cedar Basin"
    assert document.sections[0].heading == "April count"
    assert "Six boats stayed up." in document.text
    assert document.text.startswith("# Cedar Basin")


def test_plain_text_is_one_section(tmp_path: Path) -> None:
    path = tmp_path / "field.txt"
    path.write_text("The rain barrel is behind the building.\n", encoding="utf-8")
    document = ingest_text(path)
    assert document.kind == "text"
    assert document.sections[0].heading == "Overview"
    assert "rain barrel" in document.text


def test_empty_text_is_an_error(tmp_path: Path) -> None:
    path = tmp_path / "empty.md"
    path.write_text("   \n", encoding="utf-8")
    with pytest.raises(AudioOverviewError, match="No text"):
        ingest_text(path)


def test_missing_source() -> None:
    with pytest.raises(AudioOverviewError, match="not found"):
        load_source("/tmp/audio-overview-does-not-exist.md")


def test_pdf_pages_keep_order(tmp_path: Path) -> None:
    path = tmp_path / "notes.pdf"
    path.write_bytes(
        build_pdf(
            [
                "The rain barrel sits behind the workshop.",
                "In April 2024 six boats stayed afloat.",
            ]
        )
    )
    document = load_source(str(path))
    assert document.kind == "pdf"
    assert "rain barrel" in document.text
    assert "April 2024" in document.text
    assert document.text.index("rain barrel") < document.text.index("April 2024")
    assert document.sections[0].heading == "Page 1"
    assert document.sections[1].heading == "Page 2"


def test_blank_pdf_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "blank.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    with path.open("wb") as handle:
        writer.write(handle)
    with pytest.raises(AudioOverviewError, match="No extractable text"):
        load_source(str(path))


def test_html_article_drops_navigation() -> None:
    html = (FIXTURES / "article.html").read_text(encoding="utf-8")
    document = article_from_html(html, "https://example.test/cedar")
    assert document.kind == "url"
    assert document.title == "Cedar Basin Notes"
    assert "rain barrel" in document.text
    assert "April 2024" in document.text
    assert "Home | Shop" not in document.text
    assert "Copyright example" not in document.text
    assert any(section.heading == "April count" for section in document.sections)


def test_url_ingest_uses_the_injected_fetcher() -> None:
    html = (FIXTURES / "article.html").read_bytes()
    seen: list[str] = []

    def fetch(url: str) -> tuple[str, bytes]:
        seen.append(url)
        return "text/html; charset=utf-8", html

    document = ingest_url("https://example.test/cedar", fetcher=fetch)
    assert seen == ["https://example.test/cedar"]
    assert "rain barrel" in document.text


def test_url_pdf_content_type_uses_the_pdf_path() -> None:
    payload = build_pdf(["A rain barrel fed the stone basin."])

    def fetch(url: str) -> tuple[str, bytes]:
        return "application/pdf", payload

    document = ingest_url("https://example.test/notes", fetcher=fetch)
    assert document.kind == "pdf"
    assert "rain barrel" in document.text


def test_repo_summary_includes_readme_and_skips_dependencies(tmp_path: Path) -> None:
    root = tmp_path / "demo"
    (root / "src").mkdir(parents=True)
    (root / ".git").mkdir()
    (root / "README.md").write_text("# Demo Kit\n\nA kit for 12 dollars.\n", encoding="utf-8")
    (root / "src" / "fold.py").write_text(
        '"""Fold a skiff."""\n\ndef fold_skiff(sheet: str) -> int:\n    return 14\n',
        encoding="utf-8",
    )
    noise = root / "node_modules" / "leftpad"
    noise.mkdir(parents=True)
    (noise / "index.js").write_text("secret noise", encoding="utf-8")
    (root / "src" / "blob.dat").write_bytes(b"\x00binary")
    document = load_source(str(root))
    assert document.kind == "repo"
    assert document.metadata["git"] == "yes"
    assert document.title == "Demo Kit"
    assert "12 dollars" in document.text
    assert "fold_skiff" in document.text
    assert "secret noise" not in document.text
    assert "src/fold.py" in document.text
    assert "node_modules" not in document.text


def test_directory_without_git_is_still_summarized(tmp_path: Path) -> None:
    root = tmp_path / "loose"
    root.mkdir()
    (root / "README.md").write_text("# Loose notes\n\nThe basin is stone.\n", encoding="utf-8")
    document = load_source(str(root))
    assert document.metadata["git"] == "no"
    assert "stone" in document.text
