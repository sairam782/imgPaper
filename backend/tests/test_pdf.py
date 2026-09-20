import pytest
from conftest import FIXTURES

from app.ingest import PdfError, extract_pdf_text, sectionize

SAMPLE = FIXTURES / "sample_paper.pdf"


def test_extracts_text_from_a_real_pdf():
    text, pages = extract_pdf_text(SAMPLE.read_bytes())
    assert pages >= 1
    assert "sparse routing" in text.lower()


def test_sectionizes_an_extracted_pdf():
    text, _ = extract_pdf_text(SAMPLE.read_bytes())
    paper = sectionize(text)
    headings = [s.heading for s in paper.sections]

    assert "Abstract" in headings
    assert "Method" in headings
    assert "Results" in headings
    assert "References" not in headings
    assert paper.title_guess.startswith("Sparse Routing")
    assert paper.word_count > 500


def test_rejects_non_pdf_bytes():
    with pytest.raises(PdfError, match="does not look like a PDF"):
        extract_pdf_text(b"this is plainly not a pdf")


def test_respects_the_page_budget():
    _, pages = extract_pdf_text(SAMPLE.read_bytes(), max_pages=1)
    assert pages == 1
