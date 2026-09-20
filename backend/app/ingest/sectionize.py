"""Turn a wall of extracted PDF text back into sections.

PDF text extraction loses structure, so this rebuilds enough of it that the
model receives a paper rather than a blob: headings, ordered sections, and a
reference list cut off the end.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Canonical section names, in the order they usually appear. Used both to
# recognise unnumbered headings and to score how paper-like a line is.
KNOWN_HEADINGS = (
    "abstract", "introduction", "background", "related work", "preliminaries",
    "motivation", "problem statement", "method", "methods", "methodology",
    "approach", "model", "architecture", "our approach", "framework",
    "implementation", "experimental setup", "experiments", "evaluation",
    "results", "analysis", "ablation", "ablation study", "ablations",
    "discussion", "limitations", "future work", "conclusion", "conclusions",
    "acknowledgments", "acknowledgements", "references", "bibliography",
    "appendix", "supplementary material",
)

_END_SECTIONS = ("references", "bibliography")

# "3 Method", "3.1. Self-Attention", "IV. Results"
_NUMBERED = re.compile(
    r"^\s*(?:(\d+(?:\.\d+)*)|([IVXLC]{1,5}))[.)]?\s+([A-Z][^\n]{2,70})$"
)
_ROMAN = re.compile(r"^[IVXLC]{1,5}$")
# A hyphen splitting a word across lines: "atten-\ntion" -> "attention".
_HYPHEN_BREAK = re.compile(r"([A-Za-z])-\n([a-z])")
_BULLET = re.compile(r"^\s*[-•·*]\s+")


@dataclass
class Section:
    heading: str
    text: str
    level: int = 1
    number: str | None = None

    @property
    def word_count(self) -> int:
        return len(self.text.split())


@dataclass
class ParsedPaper:
    sections: list[Section] = field(default_factory=list)
    title_guess: str | None = None
    dropped_references: bool = False

    @property
    def word_count(self) -> int:
        return sum(s.word_count for s in self.sections)


def _normalise_heading(line: str) -> str:
    return re.sub(r"[^a-z ]", "", line.lower()).strip()


def _is_known_heading(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) > 60:
        return False
    normalised = _normalise_heading(stripped)
    if not normalised:
        return False
    if normalised in KNOWN_HEADINGS:
        return True
    # "5 CONCLUSION" / "III. Results" style. The separator is required: without
    # it, "Conclusion" parses as the roman numeral C followed by "onclusion".
    trimmed = re.sub(r"^\s*(?:\d+(?:\.\d+)*|[IVXLC]{1,5})(?:[.)]\s*|\s+)", "", stripped)
    return _normalise_heading(trimmed) in KNOWN_HEADINGS


@dataclass
class Heading:
    """A recognised heading, already separated from its section number."""

    title: str
    number: str | None
    level: int


def _looks_like_heading(line: str) -> Heading | None:
    """Recognise a heading and return it with the numbering stripped.

    The title is taken from the match itself rather than re-stripped
    afterwards, so an unnumbered heading is never partly eaten.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 80:
        return None
    if stripped.endswith((".", ",", ";", ":")) and not _is_known_heading(stripped):
        return None

    match = _NUMBERED.match(stripped)
    if match:
        number = match.group(1) or match.group(2)
        body = match.group(3).strip()
        # Guard against sentences that merely start with a number.
        if body.count(" ") <= 8 or _is_known_heading(body):
            level = 1 if _ROMAN.fullmatch(number) else number.count(".") + 1
            return Heading(title=body, number=number, level=level)

    if _is_known_heading(stripped):
        return Heading(title=stripped, number=None, level=1)

    # ALL CAPS short line, e.g. "METHOD" with no number.
    letters = [c for c in stripped if c.isalpha()]
    if letters and len(stripped) < 45 and all(c.isupper() for c in letters):
        if 1 <= len(stripped.split()) <= 6:
            return Heading(title=stripped, number=None, level=1)

    return None


def _join_paragraphs(lines: list[str]) -> str:
    """Re-flow hard-wrapped PDF lines into paragraphs."""
    text = "\n".join(lines)
    text = _HYPHEN_BREAK.sub(r"\1\2", text)

    out: list[str] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            out.append(" ".join(buffer).strip())
            buffer.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if _BULLET.match(raw):
            flush()
            out.append(raw.strip())
            continue
        buffer.append(line)
        # A line ending in sentence punctuation that is also short probably
        # ended a paragraph rather than being wrapped.
        if line.endswith((".", "!", "?")) and len(line) < 60:
            flush()
    flush()
    return "\n\n".join(p for p in out if p)


def strip_references(sections: list[Section]) -> tuple[list[Section], bool]:
    """Drop the reference list and everything after it."""
    for index, section in enumerate(sections):
        if _normalise_heading(section.heading) in _END_SECTIONS:
            return sections[:index], True
    return sections, False


_AFFILIATION = re.compile(
    r"universit|institute|department|laborator|\blab\b|college|school of|inc\.|corp\.",
    re.IGNORECASE,
)


def _looks_like_authors(line: str) -> bool:
    """An author line is capitalised names joined by commas or 'and'."""
    if "@" in line or _AFFILIATION.search(line):
        return True
    if "," not in line and " and " not in line:
        return False
    parts = [p.strip() for p in re.split(r",| and ", line) if p.strip()]
    if len(parts) < 2:
        return False
    namelike = sum(
        1
        for part in parts
        if 1 <= len(part.split()) <= 4 and part[:1].isupper() and part.lower() == part.lower()
    )
    return namelike >= len(parts) - 1


def _title_candidate(line: str) -> bool:
    stripped = line.strip()
    if len(stripped) < 3 or len(stripped) > 200:
        return False
    if _is_known_heading(stripped) or "@" in stripped:
        return False
    if stripped.lower().startswith("arxiv"):
        return False
    return sum(c.isdigit() for c in stripped) <= len(stripped) / 4


def _guess_title(lines: list[str]) -> str | None:
    """Reassemble the title from the first substantial lines of page one.

    PDF extraction hard-wraps the title, so the first line is often only half
    of it. Continuation lines are joined until something that is clearly not
    part of a title turns up -- an author list, an affiliation, or a heading.
    """
    start = None
    for index, raw in enumerate(lines[:25]):
        line = raw.strip()
        if len(line) < 12 or not _title_candidate(line) or _looks_like_authors(line):
            continue
        start = index
        break

    if start is None:
        return None

    parts = [lines[start].strip()]
    for raw in lines[start + 1 : start + 4]:
        line = raw.strip()
        if not line:
            break
        if parts[-1].endswith((".", "?", "!")):
            break
        if not _title_candidate(line) or _looks_like_authors(line):
            break
        if len(" ".join(parts)) + len(line) > 200:
            break
        parts.append(line)

    return " ".join(parts)


def sectionize(text: str, *, keep_references: bool = False) -> ParsedPaper:
    """Split extracted paper text into ordered sections."""
    lines = text.splitlines()
    paper = ParsedPaper(title_guess=_guess_title(lines))

    current_heading = "Front matter"
    current_number: str | None = None
    current_level = 1
    buffer: list[str] = []

    def close() -> None:
        body = _join_paragraphs(buffer)
        if body.strip():
            paper.sections.append(
                Section(
                    heading=current_heading,
                    text=body,
                    level=current_level,
                    number=current_number,
                )
            )
        buffer.clear()

    for line in lines:
        heading = _looks_like_heading(line)
        if heading is not None:
            close()
            current_heading = heading.title or line.strip()
            current_number = heading.number
            current_level = heading.level
        else:
            buffer.append(line)
    close()

    if not keep_references:
        paper.sections, paper.dropped_references = strip_references(paper.sections)

    return paper
