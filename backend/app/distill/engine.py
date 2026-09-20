"""Drive the model passes that turn paper text into a Digest."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..cache import digest_id
from ..config import Settings
from ..ingest.sectionize import ParsedPaper, Section
from ..models import Digest, DigestCore, PaperMeta
from . import prompt as P

TOOL_NAME = "emit_digest"
MAX_CONDENSE_CONCURRENCY = 6
CONDENSE_MIN_WORDS = 120


class DistillError(RuntimeError):
    """Raised when the model could not be turned into a valid digest."""


def translate_api_error(exc: Exception, model: str = "") -> DistillError:
    """Turn an SDK exception into something a user can act on.

    A raw 401 traceback tells the person running this nothing about the fact
    that their key is wrong, which is the single most likely thing to go wrong
    on a first run.
    """
    try:
        import anthropic
    except ImportError:  # pragma: no cover - dependency is declared
        return DistillError(str(exc))

    if isinstance(exc, anthropic.AuthenticationError):
        return DistillError(
            "The Anthropic API rejected the key. Check ANTHROPIC_API_KEY in your "
            ".env file, then restart the server."
        )
    if isinstance(exc, anthropic.PermissionDeniedError):
        return DistillError(
            "That API key is valid but not allowed to use this model. Check the "
            "model name in PAPERPRISM_MODEL and your account's access."
        )
    if isinstance(exc, anthropic.NotFoundError):
        return DistillError(
            f"The Anthropic API has no model named '{model}'. "
            "Check PAPERPRISM_MODEL in your .env file."
        )
    if isinstance(exc, anthropic.RateLimitError):
        return DistillError(
            "Rate limited by the Anthropic API. Wait a moment and try again."
        )
    if isinstance(exc, anthropic.APIConnectionError):
        return DistillError(
            "Could not reach the Anthropic API. Check your network connection."
        )
    if isinstance(exc, anthropic.APIStatusError):
        return DistillError(f"The Anthropic API returned an error: {exc}")
    return DistillError(f"The analysis failed: {exc}")


# --------------------------------------------------------------------------
# JSON Schema plumbing
# --------------------------------------------------------------------------


def _inline_refs(node: Any, defs: dict[str, Any]) -> Any:
    """Replace every $ref with its definition.

    Pydantic emits `$defs` + `$ref`; inlining keeps the tool schema readable
    and avoids depending on how a given API version resolves references. The
    digest schema is a tree, so this terminates.
    """
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/$defs/"):
            target = defs.get(ref.rsplit("/", 1)[1], {})
            merged = {**_inline_refs(target, defs)}
            # Keep a description written at the use site; it is more specific
            # than the one on the shared definition.
            for key, value in node.items():
                if key != "$ref":
                    merged[key] = _inline_refs(value, defs)
            return merged
        return {k: _inline_refs(v, defs) for k, v in node.items() if k != "$defs"}
    if isinstance(node, list):
        return [_inline_refs(item, defs) for item in node]
    return node


def build_tool_schema() -> dict[str, Any]:
    schema = DigestCore.model_json_schema()
    defs = schema.get("$defs", {})
    inlined = _inline_refs(schema, defs)
    inlined.pop("title", None)
    return {
        "name": TOOL_NAME,
        "description": (
            "Emit the complete structured digest of the paper. Call this exactly once."
        ),
        "input_schema": inlined,
    }


# --------------------------------------------------------------------------
# Assembling the text the model sees
# --------------------------------------------------------------------------


def render_paper(paper: ParsedPaper, meta: PaperMeta) -> str:
    """Lay the paper out as headed sections with its metadata on top."""
    header = [f"TITLE: {meta.title}"]
    if meta.authors:
        shown = ", ".join(meta.authors[:12])
        if len(meta.authors) > 12:
            shown += f", and {len(meta.authors) - 12} others"
        header.append(f"AUTHORS: {shown}")
    if meta.year:
        header.append(f"YEAR: {meta.year}")
    if meta.arxiv_id:
        header.append(f"ARXIV: {meta.arxiv_id}")
    if meta.abstract:
        header.append(f"\nABSTRACT\n{meta.abstract}")

    body = "\n\n".join(f"## {s.heading}\n{s.text}" for s in paper.sections)
    return "\n".join(header) + "\n\n" + body


class Distiller:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client: Any = None
        self._tool = build_tool_schema()

    # -- client ------------------------------------------------------------

    def _get_client(self) -> Any:
        if self._client is None:
            if not self.settings.api_key:
                raise DistillError(
                    "No ANTHROPIC_API_KEY is set, so live papers cannot be analysed. "
                    "Set one, or explore the bundled demo paper."
                )
            try:
                from anthropic import AsyncAnthropic
            except ImportError as exc:  # pragma: no cover - dependency is declared
                raise DistillError("The anthropic package is not installed.") from exc
            self._client = AsyncAnthropic(api_key=self.settings.api_key)
        return self._client

    # -- pass 1: condensation ---------------------------------------------

    async def _condense_section(self, section: Section, sem: asyncio.Semaphore) -> Section:
        if section.word_count < CONDENSE_MIN_WORDS:
            return section
        client = self._get_client()
        async with sem:
            try:
                message = await client.messages.create(
                    model=self.settings.condense_model,
                    max_tokens=1400,
                    system=P.CONDENSE_SYSTEM,
                    messages=[
                        {
                            "role": "user",
                            "content": P.CONDENSE_INSTRUCTION.format(
                                heading=section.heading, body=section.text[:60_000]
                            ),
                        }
                    ],
                )
            except Exception:
                # If condensing a section fails, a truncated original is still
                # better input than nothing.
                return Section(
                    heading=section.heading,
                    text=section.text[:6_000],
                    level=section.level,
                    number=section.number,
                )

        text = "".join(
            block.text for block in message.content if getattr(block, "type", "") == "text"
        ).strip()
        return Section(
            heading=section.heading,
            text=text or section.text[:6_000],
            level=section.level,
            number=section.number,
        )

    async def condense(self, paper: ParsedPaper) -> ParsedPaper:
        """Shrink a long paper section by section, preserving its numbers."""
        sem = asyncio.Semaphore(MAX_CONDENSE_CONCURRENCY)
        sections = await asyncio.gather(
            *(self._condense_section(section, sem) for section in paper.sections)
        )
        return ParsedPaper(
            sections=list(sections),
            title_guess=paper.title_guess,
            dropped_references=paper.dropped_references,
        )

    # -- pass 2: the digest ------------------------------------------------

    async def _call_digest(self, messages: list[dict[str, Any]]) -> dict[str, Any]:
        client = self._get_client()
        try:
            message = await client.messages.create(
                model=self.settings.model,
                max_tokens=8_000,
                system=P.SYSTEM,
                tools=[self._tool],
                tool_choice={"type": "tool", "name": TOOL_NAME},
                messages=messages,
            )
        except DistillError:
            raise
        except Exception as exc:
            raise translate_api_error(exc, self.settings.model) from exc
        for block in message.content:
            if getattr(block, "type", "") == "tool_use" and block.name == TOOL_NAME:
                return dict(block.input)
        raise DistillError("The model replied without producing a digest.")

    async def distill(
        self,
        paper: ParsedPaper,
        meta: PaperMeta,
        *,
        truncated: bool = False,
    ) -> Digest:
        """Run the full pipeline and return a validated digest."""
        source = render_paper(paper, meta)
        condensed = False

        if len(source) > self.settings.condense_threshold:
            paper = await self.condense(paper)
            source = render_paper(paper, meta)
            condensed = True

        source = source[: self.settings.max_chars]

        instruction = P.DIGEST_INSTRUCTION.format(paper=source)
        if truncated:
            instruction += "\n\n" + P.TRUNCATION_NOTE
        if condensed:
            instruction += "\n\n" + P.CONDENSED_NOTE

        messages: list[dict[str, Any]] = [{"role": "user", "content": instruction}]

        raw = await self._call_digest(messages)
        try:
            core = DigestCore.model_validate(raw)
        except ValidationError as first_error:
            # One corrective round: the model is told exactly which fields it
            # got wrong, which fixes nearly every schema miss.
            messages += [
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "retry",
                            "name": TOOL_NAME,
                            "input": raw,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "retry",
                            "is_error": True,
                            "content": (
                                "That digest did not match the schema:\n"
                                f"{first_error}\n\n"
                                "Call emit_digest again with those fields corrected. "
                                "Keep everything that was already valid."
                            ),
                        }
                    ],
                },
            ]
            retry = await self._call_digest(messages)
            try:
                core = DigestCore.model_validate(retry)
            except ValidationError as second_error:
                raise DistillError(
                    f"The model could not produce a valid digest: {second_error}"
                ) from second_error

        return Digest(
            **core.model_dump(),
            meta=meta,
            digest_id=digest_id(source, self.settings.model),
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            model=self.settings.model,
            truncated=truncated,
            word_count=paper.word_count,
        )


def load_demo_digest(path: Path) -> Digest:
    """The bundled sample, so the app is fully explorable without an API key."""
    try:
        return Digest.model_validate_json(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        raise DistillError(f"The bundled demo digest could not be loaded: {exc}") from exc
