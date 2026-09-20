"""PaperPrism HTTP API."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__
from .cache import DigestCache
from .config import settings
from .distill import Distiller, DistillError, load_demo_digest
from .jobs import STAGES, Job, registry
from .models import Digest
from .pipeline import IngestError, analyze_pdf_bytes, analyze_source

app = FastAPI(
    title="PaperPrism",
    version=__version__,
    description="Turn a research paper into a theme map, a method diagram and a layered summary.",
)

# The API and the Vite dev server sit on different ports in development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

cache = DigestCache(settings.cache_dir)
distiller = Distiller(settings)


class AnalyzeRequest(BaseModel):
    source: str = Field(
        description="An arXiv id or URL, a direct PDF URL, or the full text of a paper."
    )


class JobRef(BaseModel):
    job_id: str


def _as_http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, IngestError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, DistillError):
        return HTTPException(status_code=503, detail=str(exc))
    return HTTPException(status_code=500, detail="Something went wrong analysing that paper.")


# --------------------------------------------------------------------------
# Status
# --------------------------------------------------------------------------


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "version": __version__,
        "live": settings.live,
        "model": settings.model if settings.live else None,
        "demo_available": settings.demo_path.is_file(),
        "cached_digests": len(cache.keys()),
        "stages": [{"id": name, "label": label} for name, label in STAGES],
    }


@app.get("/api/demo", response_model=Digest)
def demo() -> Digest:
    """The bundled sample digest, so the UI works with no API key."""
    try:
        return load_demo_digest(settings.demo_path)
    except DistillError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/digest/{digest_id}", response_model=Digest)
def get_digest(digest_id: str) -> Digest:
    found = cache.get(digest_id)
    if found is None:
        raise HTTPException(status_code=404, detail="No digest with that id.")
    return found


# --------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------


@app.post("/api/analyze", response_model=Digest)
async def analyze(request: AnalyzeRequest) -> Digest:
    """Analyse a paper and wait for the result.

    Convenient for scripts. The UI uses the job endpoints so it can show
    progress instead of a long silence.
    """
    try:
        return await analyze_source(request.source, settings, distiller, cache)
    except (IngestError, DistillError) as exc:
        raise _as_http_error(exc) from exc


@app.post("/api/jobs", response_model=JobRef, status_code=202)
async def create_job(request: AnalyzeRequest) -> JobRef:
    async def work(job: Job) -> Digest:
        return await analyze_source(request.source, settings, distiller, cache, job)

    return JobRef(job_id=registry.start(work).id)


UPLOAD_CHUNK = 1024 * 1024


async def _read_upload(file: UploadFile, limit: int) -> bytes:
    """Read an upload, refusing it as soon as it exceeds the limit.

    Reading in chunks means an oversized file is rejected after one megabyte
    rather than after it has all been buffered in memory.
    """
    chunks: list[bytes] = []
    total = 0
    while chunk := await file.read(UPLOAD_CHUNK):
        total += len(chunk)
        if total > limit:
            limit_mb = limit / (1024 * 1024)
            raise HTTPException(
                status_code=413, detail=f"PDFs must be under {limit_mb:.0f} MB."
            )
        chunks.append(chunk)
    return b"".join(chunks)


@app.post("/api/jobs/upload", response_model=JobRef, status_code=202)
async def create_upload_job(file: UploadFile = File(...)) -> JobRef:
    data = await _read_upload(file, settings.max_upload_bytes)
    if not data:
        raise HTTPException(status_code=422, detail="That file was empty.")

    filename = file.filename or "uploaded.pdf"

    async def work(job: Job) -> Digest:
        return await analyze_pdf_bytes(data, filename, settings, distiller, cache, job)

    return JobRef(job_id=registry.start(work).id)


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, Any]:
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No job with that id.")
    return job.snapshot()


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str) -> StreamingResponse:
    """Server-sent events carrying stage updates and then the digest."""
    job = registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="No job with that id.")

    async def stream() -> AsyncIterator[bytes]:
        try:
            async for snapshot in registry.watch(job):
                yield f"data: {json.dumps(snapshot)}\n\n".encode()
        except asyncio.CancelledError:  # the browser navigated away
            raise

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # stop nginx buffering the stream
        },
    )


# --------------------------------------------------------------------------
# Frontend
# --------------------------------------------------------------------------

_dist = settings.frontend_dist
if _dist.is_dir():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        """Serve the built single-page app for any non-API route."""
        candidate = (_dist / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(_dist.resolve()):
            return FileResponse(candidate)
        return FileResponse(_dist / "index.html")
