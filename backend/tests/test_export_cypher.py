"""The Cypher export has to produce something Neo4j will actually accept."""

import json

import pytest

from app.config import settings
from app.distill import load_demo_digest
from app.export_cypher import quote, rel_type, to_cypher, variable
from app.models import ThemeMap

DEMO = load_demo_digest(settings.demo_path)


def test_every_node_becomes_a_labelled_create():
    cypher = to_cypher(DEMO.theme_map)
    assert cypher.count("CREATE (") == len(DEMO.theme_map.nodes) + len(DEMO.theme_map.edges)
    assert ":Idea:CoreIdea" in cypher
    assert ":Idea:Problem" in cypher
    assert "name: 'Self-attention'" in cypher


def test_relationships_use_the_node_variables():
    cypher = to_cypher(DEMO.theme_map)
    assert "(selfattn)-[:REMOVES {label: 'removes'}]->(sequential)" in cypher


@pytest.mark.parametrize(
    "label,expected",
    [
        ("is built from", "IS_BUILT_FROM"),
        ("replaces", "REPLACES"),
        ("scaled by sqrt(d_k)", "SCALED_BY_SQRT_D_K"),
        ("", "RELATED_TO"),
        ("2x faster", "R2X_FASTER"),
    ],
)
def test_relationship_types_are_valid_identifiers(label, expected):
    assert rel_type(label) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("plain", "'plain'"),
        ("it's here", r"'it\'s here'"),
        ("back\\slash", r"'back\\slash'"),
        ("two\nlines", r"'two\nlines'"),
    ],
)
def test_string_literals_are_escaped(raw, expected):
    assert quote(raw) == expected


def test_variables_are_unique_and_identifier_safe():
    used: set[str] = set()
    assert variable("self-attn", used) == "self_attn"
    assert variable("self attn", used) == "self_attn_2", "a collision must not shadow"
    assert variable("2nd-idea", used) == "n2nd_idea", "cannot start with a digit"
    assert variable("!!!", used) == "n"


def test_edges_to_unknown_nodes_are_dropped():
    payload = json.loads(settings.demo_path.read_text())["theme_map"]
    payload["edges"].append({"source": "ghost", "target": "transformer", "label": "haunts"})
    cypher = to_cypher(ThemeMap.model_validate(payload))
    assert "HAUNTS" not in cypher


def test_a_title_is_emitted_as_a_comment():
    cypher = to_cypher(DEMO.theme_map, title="Attention Is All You Need")
    assert cypher.startswith("// Attention Is All You Need")


def test_output_has_no_unescaped_quotes_inside_literals():
    # A stray quote would end a literal early and corrupt the statement.
    for line in to_cypher(DEMO.theme_map).splitlines():
        if line.startswith("//") or not line:
            continue
        body = line
        # Remove properly escaped quotes, then count what is left.
        assert body.replace(r"\'", "").count("'") % 2 == 0
