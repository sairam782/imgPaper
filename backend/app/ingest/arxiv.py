"""Resolve an arXiv reference to metadata plus the PDF bytes."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx

from ..models import PaperMeta

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_API = "https://export.arxiv.org/api/query"

# Matches the bare id in anything from "1706.03762" to
# "https://arxiv.org/pdf/1706.03762v5.pdf" to "arXiv:math.GT/0309136".
_NEW_STYLE = re.compile(r"(?<!\d)(\d{4}\.\d{4,5})(v\d+)?")
_OLD_STYLE = re.compile(r"([a-z-]+(?:\.[A-Z]{2})?/\d{7})(v\d+)?")


class ArxivError(RuntimeError):
    pass


@dataclass
class ArxivPaper:
    meta: PaperMeta
    pdf_url: str


def parse_arxiv_id(raw: str) -> str | None:
    """Pull an arXiv id out of an id, an abs/pdf URL, or a citation string.

    Returns the id without the version suffix, or None if there isn't one.
    """
    if not raw:
        return None
    text = raw.strip()
    match = _NEW_STYLE.search(text) or _OLD_STYLE.search(text)
    return match.group(1) if match else None


def _text(node: ET.Element | None) -> str | None:
    if node is None or node.text is None:
        return None
    return " ".join(node.text.split()) or None


def _parse_feed(xml: str, arxiv_id: str) -> ArxivPaper:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:  # pragma: no cover - malformed upstream response
        raise ArxivError(f"arXiv returned unparseable XML: {exc}") from exc

    entry = root.find(f"{ATOM}entry")
    if entry is None:
        raise ArxivError(f"arXiv has no record for {arxiv_id}")
    # The API answers a bad id with a single entry whose title is "Error".
    title = _text(entry.find(f"{ATOM}title"))
    if title in (None, "Error"):
        raise ArxivError(f"arXiv has no record for {arxiv_id}")

    published = _text(entry.find(f"{ATOM}published")) or ""
    year = int(published[:4]) if published[:4].isdigit() else None

    authors = [
        name
        for author in entry.findall(f"{ATOM}author")
        if (name := _text(author.find(f"{ATOM}name")))
    ]

    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
    for link in entry.findall(f"{ATOM}link"):
        if link.get("title") == "pdf" and link.get("href"):
            pdf_url = link.get("href")  # type: ignore[assignment]
            break

    meta = PaperMeta(
        title=title,
        authors=authors,
        year=year,
        arxiv_id=arxiv_id,
        source_url=f"https://arxiv.org/abs/{arxiv_id}",
        abstract=_text(entry.find(f"{ATOM}summary")),
    )
    return ArxivPaper(meta=meta, pdf_url=pdf_url)


async def fetch_arxiv(arxiv_id: str, *, timeout: float = 30.0) -> tuple[ArxivPaper, bytes]:
    """Fetch metadata and PDF bytes for an arXiv id."""
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=True, headers={"User-Agent": "PaperPrism/0.1"}
    ) as client:
        try:
            resp = await client.get(
                ARXIV_API, params={"id_list": arxiv_id, "max_results": 1}
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ArxivError(f"Could not reach the arXiv API: {exc}") from exc

        paper = _parse_feed(resp.text, arxiv_id)

        try:
            pdf_resp = await client.get(paper.pdf_url)
            pdf_resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise ArxivError(f"Could not download the PDF for {arxiv_id}: {exc}") from exc

    return paper, pdf_resp.content
