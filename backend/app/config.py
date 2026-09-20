"""Runtime configuration, all overridable by environment variable."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_dotenv(path: Path | None = None) -> None:
    """Read a .env file into the environment.

    Hand-rolled rather than pulling in python-dotenv, because the whole job is
    twenty lines and one fewer dependency is worth more than the edge cases a
    library would cover. A variable already set in the real environment always
    wins, so `ANTHROPIC_API_KEY=... make serve` overrides the file.
    """
    env_file = path or REPO_ROOT / ".env"
    try:
        lines = env_file.read_text("utf-8").splitlines()
    except OSError:
        return  # no .env is the normal case, not an error

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        stripped = stripped.removeprefix("export ").lstrip()
        key, separator, value = stripped.partition("=")
        if not separator:
            continue
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw).expanduser() if raw else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    api_key: str | None
    model: str
    condense_model: str
    cache_dir: Path
    demo_path: Path
    frontend_dist: Path
    # Papers longer than this many characters get condensed section-by-section
    # before the digest pass, instead of being sent whole.
    condense_threshold: int
    max_chars: int
    max_upload_bytes: int

    @property
    def live(self) -> bool:
        """Whether real model calls are possible."""
        return bool(self.api_key)


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        api_key=os.environ.get("ANTHROPIC_API_KEY") or None,
        model=os.environ.get("PAPERPRISM_MODEL", "claude-sonnet-5"),
        condense_model=os.environ.get("PAPERPRISM_CONDENSE_MODEL", "claude-haiku-4-5-20251001"),
        cache_dir=_env_path("PAPERPRISM_CACHE_DIR", REPO_ROOT / ".cache" / "digests"),
        demo_path=_env_path("PAPERPRISM_DEMO_PATH", REPO_ROOT / "data" / "demo" / "attention.json"),
        frontend_dist=_env_path("PAPERPRISM_FRONTEND_DIST", REPO_ROOT / "frontend" / "dist"),
        condense_threshold=_env_int("PAPERPRISM_CONDENSE_THRESHOLD", 90_000),
        max_chars=_env_int("PAPERPRISM_MAX_CHARS", 400_000),
        max_upload_bytes=_env_int("PAPERPRISM_MAX_UPLOAD_BYTES", 25 * 1024 * 1024),
    )


settings = load_settings()
