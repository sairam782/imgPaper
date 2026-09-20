import pytest

from app.cache import DigestCache
from app.config import settings
from app.distill import load_demo_digest
from app.pipeline import IngestError, analyze_source, resolve_source


class StubDistiller:
    """Stands in for the model so the pipeline can be tested offline."""

    def __init__(self, digest):
        self.digest = digest
        self.calls = 0

    async def distill(self, paper, meta, *, truncated=False):
        self.calls += 1
        self.digest.meta = meta
        return self.digest


@pytest.fixture
def digest():
    return load_demo_digest(settings.demo_path)


PAPER_TEXT = (
    "Sparse Routing for Small Models\n"
    "Abstract\n"
    "We introduce sparse routing, which sends each token to one of k experts. " * 3
    + "\n1 Introduction\n"
    + "Dense training wastes capacity on easy tokens. " * 30
    + "\n2 Method\n"
    + "A learned router assigns every token to a single expert block. " * 30
)


async def test_pasted_text_is_accepted():
    parsed, meta, truncated = await resolve_source(PAPER_TEXT, settings)
    assert truncated is False
    assert "Introduction" in [s.heading for s in parsed.sections]
    assert meta.title.startswith("Sparse Routing")


async def test_empty_input_is_rejected():
    with pytest.raises(IngestError, match="arXiv link"):
        await resolve_source("   ", settings)


async def test_short_unrecognised_input_is_rejected():
    with pytest.raises(IngestError, match="could not make sense"):
        await resolve_source("explain this paper to me", settings)


async def test_result_is_cached_and_reused(tmp_path, digest):
    cache = DigestCache(tmp_path)
    stub = StubDistiller(digest)

    first = await analyze_source(PAPER_TEXT, settings, stub, cache)
    second = await analyze_source(PAPER_TEXT, settings, stub, cache)

    assert stub.calls == 1, "the second call should have hit the cache"
    assert first.digest_id == second.digest_id
    assert cache.get(first.digest_id) is not None


async def test_cache_key_covers_the_paper_text(tmp_path, digest):
    cache = DigestCache(tmp_path)
    stub = StubDistiller(digest)

    await analyze_source(PAPER_TEXT, settings, stub, cache)
    await analyze_source(PAPER_TEXT + "\n3 Results\nPerplexity fell. " * 20, settings, stub, cache)

    assert stub.calls == 2, "a different paper must not reuse a cached digest"
