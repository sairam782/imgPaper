"""Exercise the model-facing path with a stand-in client.

These cover the parts that only run when an API key is present: the forced
tool call, the corrective retry, and the condensation pass for long papers.
"""

import dataclasses
import json
from types import SimpleNamespace

import pytest

from app.config import settings
from app.distill import DistillError
from app.distill.engine import Distiller
from app.ingest.sectionize import ParsedPaper, Section
from app.models import PaperMeta

VALID = json.loads(settings.demo_path.read_text())
CORE_FIELDS = {
    key: VALID[key]
    for key in (
        "theme", "tldr", "problem", "key_idea", "summary", "contributions",
        "theme_map", "method", "results", "limitations", "glossary",
        "prereqs", "sections", "reading_path", "checks",
    )
}

META = PaperMeta(title="A Paper", authors=["A. Author"], year=2024)


def tool_use(payload):
    return SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", name="emit_digest", input=payload)]
    )


def text_block(body):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=body)])


class FakeClient:
    """Returns queued responses and records what it was asked."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("the client was called more times than expected")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def make(responses, **overrides):
    distiller = Distiller(dataclasses.replace(settings, api_key="test-key", **overrides))
    client = FakeClient(responses)
    distiller._client = client
    return distiller, client


def paper(sections=None):
    return ParsedPaper(
        sections=sections or [Section("Introduction", "We begin the work. " * 20)]
    )


async def test_produces_a_digest_from_a_tool_call():
    distiller, client = make([tool_use(CORE_FIELDS)])
    digest = await distiller.distill(paper(), META)

    assert digest.meta.title == "A Paper"
    assert digest.theme == VALID["theme"]
    assert digest.model == distiller.settings.model
    assert len(client.calls) == 1

    call = client.calls[0]
    assert call["tool_choice"] == {"type": "tool", "name": "emit_digest"}
    assert call["tools"][0]["name"] == "emit_digest"
    assert "A Paper" in call["messages"][0]["content"]


async def test_invalid_output_is_corrected_on_a_second_attempt():
    broken = {**CORE_FIELDS, "summary": {"eli5": "just this one"}}
    distiller, client = make([tool_use(broken), tool_use(CORE_FIELDS)])

    digest = await distiller.distill(paper(), META)

    assert digest.summary.overview == VALID["summary"]["overview"]
    assert len(client.calls) == 2

    # The retry must tell the model what was wrong, as a tool result.
    retry = client.calls[1]["messages"][-1]["content"][0]
    assert retry["type"] == "tool_result"
    assert retry["is_error"] is True
    assert "summary" in retry["content"]


async def test_two_invalid_attempts_raise_rather_than_return_junk():
    broken = {"theme": "not nearly enough"}
    distiller, _ = make([tool_use(broken), tool_use(broken)])

    with pytest.raises(DistillError, match="could not produce a valid digest"):
        await distiller.distill(paper(), META)


async def test_a_reply_without_a_tool_call_is_an_error():
    distiller, _ = make([text_block("I would rather just chat about it.")])

    with pytest.raises(DistillError, match="without producing a digest"):
        await distiller.distill(paper(), META)


async def test_missing_api_key_is_reported_clearly():
    distiller = Distiller(dataclasses.replace(settings, api_key=None))
    with pytest.raises(DistillError, match="ANTHROPIC_API_KEY"):
        await distiller.distill(paper(), META)


async def test_long_papers_are_condensed_before_the_digest_pass():
    sections = [Section(f"Section {i}", "Substantive content here. " * 400) for i in range(4)]
    distiller, client = make(
        [text_block(f"condensed {i}") for i in range(4)] + [tool_use(CORE_FIELDS)],
        condense_threshold=2_000,
    )

    digest = await distiller.distill(paper(sections), META)

    assert digest.theme == VALID["theme"]
    assert len(client.calls) == 5, "one condense call per section, then the digest"

    condense_models = {call["model"] for call in client.calls[:4]}
    assert condense_models == {distiller.settings.condense_model}

    final = client.calls[-1]["messages"][0]["content"]
    assert "condensed 0" in final
    assert "faithful section-by-section condensation" in final


async def test_short_sections_are_not_sent_for_condensing():
    sections = [
        Section("Tiny", "Three words only."),
        Section("Long", "Plenty of substantive content here. " * 400),
    ]
    distiller, client = make(
        [text_block("condensed long"), tool_use(CORE_FIELDS)], condense_threshold=2_000
    )

    await distiller.distill(paper(sections), META)

    assert len(client.calls) == 2, "the short section should be passed through as-is"


async def test_a_failed_condense_falls_back_to_the_original_text():
    sections = [Section("Body", "Original wording that must survive. " * 400)]
    distiller, client = make(
        [RuntimeError("upstream is down"), tool_use(CORE_FIELDS)], condense_threshold=2_000
    )

    digest = await distiller.distill(paper(sections), META)

    assert digest.theme == VALID["theme"]
    assert "Original wording that must survive" in client.calls[-1]["messages"][0]["content"]


async def test_truncation_is_flagged_to_the_model_and_on_the_digest():
    distiller, client = make([tool_use(CORE_FIELDS)])
    digest = await distiller.distill(paper(), META, truncated=True)

    assert digest.truncated is True
    assert "stops" in client.calls[0]["messages"][0]["content"]


# -- how failures reach the person running the server ----------------------


def api_error(kind, status):
    """Build a real SDK exception without touching the network."""
    import httpx

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status, request=request, json={"error": {"message": "nope"}})
    return kind("nope", response=response, body=None)


async def test_an_invalid_key_says_so_plainly():
    import anthropic

    distiller, _ = make([api_error(anthropic.AuthenticationError, 401)])
    with pytest.raises(DistillError, match="ANTHROPIC_API_KEY"):
        await distiller.distill(paper(), META)


async def test_an_unknown_model_names_the_setting_to_change():
    import anthropic

    distiller, _ = make([api_error(anthropic.NotFoundError, 404)], model="claude-nope")
    with pytest.raises(DistillError, match="PAPERPRISM_MODEL"):
        await distiller.distill(paper(), META)


async def test_rate_limiting_is_reported_as_temporary():
    import anthropic

    distiller, _ = make([api_error(anthropic.RateLimitError, 429)])
    with pytest.raises(DistillError, match="[Rr]ate limited"):
        await distiller.distill(paper(), META)


async def test_an_unreachable_api_is_reported_as_a_network_problem():
    import anthropic
    import httpx

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    distiller, _ = make([anthropic.APIConnectionError(request=request)])
    with pytest.raises(DistillError, match="Could not reach"):
        await distiller.distill(paper(), META)
