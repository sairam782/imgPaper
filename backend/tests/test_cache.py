import json

from app.cache import DigestCache, digest_id
from app.config import settings
from app.distill import load_demo_digest


def test_digest_id_is_stable_and_model_sensitive():
    a = digest_id("some paper text", "model-a")
    assert a == digest_id("some paper text", "model-a")
    assert a != digest_id("some paper text", "model-b")
    assert a != digest_id("other paper text", "model-a")


def test_roundtrip(tmp_path):
    cache = DigestCache(tmp_path)
    digest = load_demo_digest(settings.demo_path)

    assert cache.get("nope") is None
    cache.put("k1", digest)

    restored = cache.get("k1")
    assert restored is not None
    assert restored.meta.title == digest.meta.title
    assert len(restored.theme_map.nodes) == len(digest.theme_map.nodes)
    assert cache.keys() == ["k1"]


def test_corrupt_entry_is_ignored_not_raised(tmp_path):
    cache = DigestCache(tmp_path)
    (tmp_path / "broken.json").write_text("{not json")
    assert cache.get("broken") is None


def test_entry_missing_required_fields_is_ignored(tmp_path):
    cache = DigestCache(tmp_path)
    (tmp_path / "partial.json").write_text(json.dumps({"tldr": "only this"}))
    assert cache.get("partial") is None


def test_put_survives_an_unwritable_directory(tmp_path):
    # Caching must never be the reason a good response fails.
    cache = DigestCache(tmp_path / "file-in-the-way" / "sub")
    (tmp_path / "file-in-the-way").write_text("not a directory")
    cache.put("k", load_demo_digest(settings.demo_path))
    assert cache.get("k") is None
