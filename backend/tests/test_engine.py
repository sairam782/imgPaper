import json

import pytest
from pydantic import ValidationError

from app.config import settings
from app.distill import load_demo_digest
from app.distill.engine import build_tool_schema, render_paper
from app.ingest.sectionize import ParsedPaper, Section
from app.models import DigestCore, PaperMeta


def test_tool_schema_is_fully_inlined():
    schema = build_tool_schema()
    encoded = json.dumps(schema)
    assert "$ref" not in encoded
    assert "$defs" not in encoded
    assert schema["name"] == "emit_digest"


def test_tool_schema_covers_every_digest_field():
    props = build_tool_schema()["input_schema"]["properties"]
    assert set(props) == set(DigestCore.model_fields)
    # Nested descriptions must survive inlining, since they carry the prompt.
    assert props["theme_map"]["properties"]["nodes"]["items"]["properties"]["kind"]["description"]


def test_demo_digest_satisfies_the_model_contract():
    digest = load_demo_digest(settings.demo_path)
    node_ids = {n.id for n in digest.theme_map.nodes}

    assert sum(1 for n in digest.theme_map.nodes if n.kind == "core") == 1
    for edge in digest.theme_map.edges:
        assert edge.source in node_ids
        assert edge.target in node_ids

    linked = {e.source for e in digest.theme_map.edges} | {
        e.target for e in digest.theme_map.edges
    }
    assert node_ids == linked, "every node must appear on the map"


def test_render_paper_includes_metadata_and_headings():
    paper = ParsedPaper(
        sections=[Section("Introduction", "We begin."), Section("Method", "We proceed.")]
    )
    meta = PaperMeta(title="A Title", authors=["A. Author"], year=2020, abstract="Short.")
    rendered = render_paper(paper, meta)

    assert "TITLE: A Title" in rendered
    assert "AUTHORS: A. Author" in rendered
    assert "YEAR: 2020" in rendered
    assert "## Introduction" in rendered
    assert "## Method" in rendered


def test_render_paper_abbreviates_long_author_lists():
    meta = PaperMeta(title="T", authors=[f"Author {i}" for i in range(20)])
    rendered = render_paper(ParsedPaper(sections=[Section("Body", "x")]), meta)
    assert "and 8 others" in rendered


@pytest.mark.parametrize("field", ["theme", "tldr", "summary", "theme_map", "results"])
def test_digest_core_requires_its_load_bearing_fields(field):
    payload = json.loads(settings.demo_path.read_text())
    payload.pop(field)
    with pytest.raises(ValidationError):
        DigestCore.model_validate(payload)
