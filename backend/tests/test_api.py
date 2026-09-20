import asyncio

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import settings
from app.distill import load_demo_digest
from app.pipeline import IngestError

client = TestClient(main.app)


@pytest.fixture
def demo_digest():
    return load_demo_digest(settings.demo_path)


def _drain(job_id: str, timeout: float = 5.0) -> dict:
    """Poll a job to completion. The background task runs on the app's loop."""
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload = client.get(f"/api/jobs/{job_id}").json()
        if payload["status"] != "running":
            return payload
        time.sleep(0.02)
    raise AssertionError(f"job {job_id} never finished")


def test_health_reports_capability():
    body = client.get("/api/health").json()
    assert body["ok"] is True
    assert body["demo_available"] is True
    assert isinstance(body["live"], bool)
    assert [s["id"] for s in body["stages"]][-1] == "done"


def test_demo_endpoint_returns_a_full_digest():
    body = client.get("/api/demo").json()
    assert body["meta"]["title"] == "Attention Is All You Need"
    assert body["theme_map"]["nodes"]
    assert body["method"]
    assert body["summary"]["eli5"]


def test_unknown_digest_is_404():
    assert client.get("/api/digest/does-not-exist").status_code == 404


def test_unknown_job_is_404():
    assert client.get("/api/jobs/nope").status_code == 404
    assert client.get("/api/jobs/nope/events").status_code == 404


def test_job_runs_to_completion(monkeypatch, demo_digest):
    async def fake(source, settings_, distiller, cache, job=None):
        if job:
            job.advance("distilling", "Building the digest")
        await asyncio.sleep(0)
        return demo_digest

    monkeypatch.setattr(main, "analyze_source", fake)

    created = client.post("/api/jobs", json={"source": "1706.03762"})
    assert created.status_code == 202

    final = _drain(created.json()["job_id"])
    assert final["status"] == "done"
    assert final["stage"] == "done"
    assert final["digest"]["meta"]["title"] == "Attention Is All You Need"


def test_job_reports_a_failure_instead_of_hanging(monkeypatch):
    async def fake(source, settings_, distiller, cache, job=None):
        raise IngestError("that is not a paper")

    monkeypatch.setattr(main, "analyze_source", fake)

    job_id = client.post("/api/jobs", json={"source": "gibberish"}).json()["job_id"]
    final = _drain(job_id)

    assert final["status"] == "error"
    assert "not a paper" in final["error"]


def test_job_events_stream_ends_with_the_digest(monkeypatch, demo_digest):
    async def fake(source, settings_, distiller, cache, job=None):
        return demo_digest

    monkeypatch.setattr(main, "analyze_source", fake)
    job_id = client.post("/api/jobs", json={"source": "x"}).json()["job_id"]

    with client.stream("GET", f"/api/jobs/{job_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        payload = "".join(response.iter_text())

    assert '"status": "done"' in payload
    assert "Attention Is All You Need" in payload


def test_analyze_surfaces_ingest_errors_as_422(monkeypatch):
    async def fake(source, settings_, distiller, cache, job=None):
        raise IngestError("paste something real")

    monkeypatch.setattr(main, "analyze_source", fake)
    response = client.post("/api/analyze", json={"source": "?"})

    assert response.status_code == 422
    assert "paste something real" in response.json()["detail"]


def test_empty_upload_is_rejected():
    response = client.post(
        "/api/jobs/upload", files={"file": ("empty.pdf", b"", "application/pdf")}
    )
    assert response.status_code == 422


def test_oversized_upload_is_rejected(monkeypatch):
    import dataclasses

    monkeypatch.setattr(
        main, "settings", dataclasses.replace(settings, max_upload_bytes=1024)
    )
    big = b"%PDF-1.4" + b"0" * 5_000
    response = client.post(
        "/api/jobs/upload", files={"file": ("big.pdf", big, "application/pdf")}
    )
    assert response.status_code == 413
    assert "MB" in response.json()["detail"]


def test_upload_job_runs_the_pdf_pipeline(monkeypatch, demo_digest):
    seen = {}

    async def fake(data, filename, settings_, distiller, cache, job=None):
        seen["filename"] = filename
        seen["bytes"] = len(data)
        return demo_digest

    monkeypatch.setattr(main, "analyze_pdf_bytes", fake)
    pdf = (FIXTURE := __import__("conftest").FIXTURES / "sample_paper.pdf").read_bytes()

    created = client.post(
        "/api/jobs/upload", files={"file": (FIXTURE.name, pdf, "application/pdf")}
    )
    final = _drain(created.json()["job_id"])

    assert final["status"] == "done"
    assert seen["filename"] == "sample_paper.pdf"
    assert seen["bytes"] == len(pdf)
