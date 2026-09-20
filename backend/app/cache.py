"""Content-addressed digest cache.

Digests are expensive and deterministic enough to reuse, so the same paper
resolves instantly on a second visit and repeated demos cost nothing.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import Digest


def digest_id(source_text: str, model: str) -> str:
    """A stable id for (paper content, model) so a model change re-runs."""
    payload = f"{model}\x00{source_text}".encode("utf-8", "ignore")
    return hashlib.sha256(payload).hexdigest()[:16]


class DigestCache:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def _path(self, key: str) -> Path:
        return self.directory / f"{key}.json"

    def get(self, key: str) -> Digest | None:
        path = self._path(key)
        if not path.is_file():
            return None
        try:
            return Digest.model_validate_json(path.read_text("utf-8"))
        except (ValueError, OSError):
            # A stale or half-written entry is not worth failing a request over.
            return None

    def put(self, key: str, digest: Digest) -> None:
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            tmp = self._path(key).with_suffix(".tmp")
            tmp.write_text(
                json.dumps(digest.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(self._path(key))
        except OSError:
            # Caching is an optimisation; never let it break a good response.
            pass

    def keys(self) -> list[str]:
        if not self.directory.is_dir():
            return []
        return sorted(p.stem for p in self.directory.glob("*.json"))
