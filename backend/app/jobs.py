"""An in-process job registry so a slow analysis can report progress.

Analysing a paper takes tens of seconds. Rather than leave the user staring at
a spinner, each request becomes a job that publishes stage updates, which the
frontend consumes over server-sent events.

This is deliberately in-memory and single-process: it is state that is
worthless once the server restarts, and PaperPrism has no reason to be a
cluster. Swapping in Redis would mean replacing this file only.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from .models import Digest

JOB_TTL_SECONDS = 30 * 60
MAX_JOBS = 200

# Ordered so the UI can render a progress track rather than a bare label.
STAGES: tuple[tuple[str, str], ...] = (
    ("fetching", "Fetching the paper"),
    ("extracting", "Reading the PDF"),
    ("condensing", "Working through the sections"),
    ("distilling", "Building the digest"),
    ("done", "Ready"),
)
STAGE_ORDER = {name: index for index, (name, _) in enumerate(STAGES)}


@dataclass
class Job:
    id: str
    created_at: float = field(default_factory=time.monotonic)
    stage: str = "fetching"
    detail: str = "Fetching the paper"
    status: str = "running"  # running | done | error
    digest: Digest | None = None
    error: str | None = None
    _waiters: list[asyncio.Queue] = field(default_factory=list, repr=False)

    def snapshot(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "job_id": self.id,
            "status": self.status,
            "stage": self.stage,
            "detail": self.detail,
            "step": STAGE_ORDER.get(self.stage, 0),
            "total_steps": len(STAGES) - 1,
        }
        if self.error:
            payload["error"] = self.error
        if self.digest is not None:
            payload["digest"] = self.digest.model_dump(mode="json")
        return payload

    def _publish(self) -> None:
        snapshot = self.snapshot()
        for queue in self._waiters:
            queue.put_nowait(snapshot)

    def advance(self, stage: str, detail: str | None = None) -> None:
        self.stage = stage
        self.detail = detail or dict(STAGES).get(stage, stage)
        self._publish()

    def finish(self, digest: Digest) -> None:
        self.digest = digest
        self.status = "done"
        self.stage = "done"
        self.detail = "Ready"
        self._publish()

    def fail(self, message: str) -> None:
        self.status = "error"
        self.error = message
        self._publish()


class JobRegistry:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._tasks: set[asyncio.Task] = set()

    def _evict(self) -> None:
        now = time.monotonic()
        stale = [
            job_id
            for job_id, job in self._jobs.items()
            if now - job.created_at > JOB_TTL_SECONDS and job.status != "running"
        ]
        for job_id in stale:
            self._jobs.pop(job_id, None)

        if len(self._jobs) > MAX_JOBS:
            finished = sorted(
                (j for j in self._jobs.values() if j.status != "running"),
                key=lambda j: j.created_at,
            )
            for job in finished[: len(self._jobs) - MAX_JOBS]:
                self._jobs.pop(job.id, None)

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def start(self, work: Callable[[Job], Awaitable[Digest]]) -> Job:
        """Register a job and run `work` in the background."""
        self._evict()
        job = Job(id=uuid.uuid4().hex[:12])
        self._jobs[job.id] = job

        async def runner() -> None:
            try:
                digest = await work(job)
            except asyncio.CancelledError:
                job.fail("The analysis was cancelled.")
                raise
            except Exception as exc:  # surfaced to the user, so keep the text
                job.fail(str(exc) or exc.__class__.__name__)
            else:
                job.finish(digest)

        task = asyncio.create_task(runner())
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    async def watch(self, job: Job) -> AsyncIterator[dict[str, Any]]:
        """Yield the job's current state, then every update until it settles."""
        queue: asyncio.Queue = asyncio.Queue()
        job._waiters.append(queue)
        try:
            yield job.snapshot()
            if job.status != "running":
                return
            while True:
                snapshot = await queue.get()
                yield snapshot
                if snapshot["status"] != "running":
                    return
        finally:
            if queue in job._waiters:
                job._waiters.remove(queue)


registry = JobRegistry()
