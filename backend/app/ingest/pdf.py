"""Get plain text out of a PDF without dragging in native dependencies."""

from __future__ import annotations

import io
import re

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PAGES = 80


class PdfError(RuntimeError):
    pass


# Page furniture that survives extraction and confuses the sectioniser.
_PAGE_NOISE = re.compile(
    r"^\s*(?:"
    r"\d{1,3}"                                   # bare page numbers
    r"|Page\s+\d+(?:\s+of\s+\d+)?"
    r"|arXiv:\S+"
    r"|Preprint\.?\s*(?:Under review\.?)?"
    r"|Published as a conference paper.*"
    r")\s*$",
    re.IGNORECASE,
)

_LIGATURES = {
    "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "--", " ": " ",
}


def _normalise(text: str) -> str:
    for bad, good in _LIGATURES.items():
        text = text.replace(bad, good)
    return text


def _clean_page(page_text: str) -> str:
    lines = [ln.rstrip() for ln in page_text.splitlines()]
    return "\n".join(ln for ln in lines if not _PAGE_NOISE.match(ln))


def extract_pdf_text(data: bytes, *, max_pages: int = MAX_PAGES) -> tuple[str, int]:
    """Return (text, pages_read).

    Pages beyond `max_pages` are skipped; papers that long are almost always
    mostly appendix, and the caller reports the truncation to the user.
    """
    if not data[:5].startswith(b"%PDF"):
        raise PdfError("That does not look like a PDF file.")

    try:
        reader = PdfReader(io.BytesIO(data))
    except (PdfReadError, ValueError, OSError) as exc:
        raise PdfError(f"Could not open the PDF: {exc}") from exc

    if reader.is_encrypted:
        # Many arXiv PDFs are "encrypted" with an empty owner password.
        try:
            reader.decrypt("")
        except Exception as exc:  # pragma: no cover - depends on the file
            raise PdfError("That PDF is password protected.") from exc

    pages: list[str] = []
    for index, page in enumerate(reader.pages):
        if index >= max_pages:
            break
        try:
            raw = page.extract_text() or ""
        except Exception:
            # One unreadable page should not sink the whole paper.
            continue
        cleaned = _clean_page(_normalise(raw))
        if cleaned.strip():
            pages.append(cleaned)

    if not pages:
        raise PdfError(
            "No text could be extracted. This is usually a scanned PDF, which needs OCR first."
        )

    return "\n\n".join(pages), len(pages)
