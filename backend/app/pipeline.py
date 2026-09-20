"""From 'something a user pasted' to a finished Digest."""

from __future__ import annotations

import re

import httpx

from .cache import DigestCache, digest_id
from .config import Settings
from .distill import Distiller
from .distill.engine import render_paper
from .ingest import (
    ArxivError,
    PdfError,
    extract_pdf_text,
    fetch_arxiv,
    parse_arxiv_id,
    sectionize,
)
from .ingest.sectionize import ParsedPaper
from .jobs import Job
from .models import Digest, PaperMeta

MIN_PASTE_CHARS = 400
_URL = re.compile(r"^https?://", re.IGNORECASE)


class IngestError(RuntimeError):
    pass


def _first_line_title(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if len(stripped) > 10:
            return stripped[:200]
    return "Pasted paper"


async def _download(url: str, settings: Settings) -> bytes:
    async with httpx.AsyncClient(
        timeout=45.0, follow_redirects=True, headers={"User-Agent": "PaperPrism/0.1"}
    ) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise IngestError(f"Could not download that URL: {exc}") from exc

    if len(resp.content) > settings.max_upload_bytes:
        raise IngestError("That file is larger than the size limit.")
    return resp.content


def _parse_pdf(data: bytes, meta: PaperMeta) -> tuple[ParsedPaper, bool]:
    text, pages = extract_pdf_text(data)
    paper = sectionize(text)
    if not paper.sections:
        raise IngestError("The PDF had no readable body text.")
    if meta.title in (None, "", "Untitled paper") and paper.title_guess:
        meta.title = paper.title_guess
    return paper, pages >= 80


async def resolve_source(
    source: str, settings: Settings, job: Job | None = None
) -> tuple[ParsedPaper, PaperMeta, bool]:
    """Work out what the user gave us and turn it into a parsed paper."""
    text = source.strip()
    if not text:
        raise IngestError("Give me an arXiv link, a PDF URL, or the paper's text.")

    arxiv_id = parse_arxiv_id(text) if len(text) < 300 else None

    if arxiv_id:
        if job:
            job.advance("fetching", f"Fetching arXiv:{arxiv_id}")
        try:
            paper_ref, pdf_bytes = await fetch_arxiv(arxiv_id)
        except ArxivError as exc:
            raise IngestError(str(exc)) from exc
        if job:
            job.advance("extracting", "Reading the PDF")
        parsed, truncated = _parse_pdf(pdf_bytes, paper_ref.meta)
        return parsed, paper_ref.meta, truncated

    if _URL.match(text):
        if job:
            job.advance("fetching", "Downloading the document")
        data = await _download(text, settings)
        if job:
            job.advance("extracting", "Reading the PDF")
        meta = PaperMeta(source_url=text)
        try:
            parsed, truncated = _parse_pdf(data, meta)
        except PdfError as exc:
            raise IngestError(str(exc)) from exc
        return parsed, meta, truncated

    if len(text) >= MIN_PASTE_CHARS:
        if job:
            job.advance("extracting", "Reading the text")
        parsed = sectionize(text)
        meta = PaperMeta(title=parsed.title_guess or _first_line_title(text))
        return parsed, meta, False

    raise IngestError(
        "I could not make sense of that. Paste an arXiv link or id, a direct PDF "
        "URL, or the full text of the paper."
    )


async def analyze_pdf_bytes(
    data: bytes,
    filename: str,
    settings: Settings,
    distiller: Distiller,
    cache: DigestCache,
    job: Job | None = None,
) -> Digest:
    if job:
        job.advance("extracting", "Reading the PDF")
    meta = PaperMeta(title=filename.rsplit(".", 1)[0].replace("_", " ").strip() or "Uploaded paper")
    try:
        parsed, truncated = _parse_pdf(data, meta)
    except PdfError as exc:
        raise IngestError(str(exc)) from exc
    return await _finish(parsed, meta, truncated, settings, distiller, cache, job)


async def analyze_source(
    source: str,
    settings: Settings,
    distiller: Distiller,
    cache: DigestCache,
    job: Job | None = None,
) -> Digest:
    parsed, meta, truncated = await resolve_source(source, settings, job)
    return await _finish(parsed, meta, truncated, settings, distiller, cache, job)


async def _finish(
    parsed: ParsedPaper,
    meta: PaperMeta,
    truncated: bool,
    settings: Settings,
    distiller: Distiller,
    cache: DigestCache,
    job: Job | None,
) -> Digest:
    source_text = render_paper(parsed, meta)
    # Keyed on the paper as the model would first see it, so a cache hit does
    # not depend on whether the condensation pass would have run.
    key = digest_id(source_text, settings.model)

    cached = cache.get(key)
    if cached is not None:
        return cached

    if job:
        if len(source_text) > settings.condense_threshold:
            job.advance("condensing", f"Working through {len(parsed.sections)} sections")
        else:
            job.advance("distilling", "Building the digest")

    digest = await distiller.distill(parsed, meta, truncated=truncated)
    digest.digest_id = key
    cache.put(key, digest)
    return digest
