"""The Cypher export has to produce something Neo4j will actually accept."""

import pytest

from app.config import settings
from app.distill import load_demo_digest
from app.export_cypher import quote, to_cypher, variable
from app.graph_model import build_graph

DEMO = load_demo_digest(settings.demo_path)
GRAPH = build_graph(DEMO)
CYPHER = to_cypher(GRAPH, title=DEMO.meta.title)


def test_every_node_and_relationship_is_created():
    assert CYPHER.count("CREATE (") == len(GRAPH.nodes) + len(GRAPH.edges)


def test_it_exports_the_whole_paper_not_just_the_concepts():
    for label in ("Paper", "Concept", "Step", "Artifact", "Metric", "Contribution"):
        assert f":{label} {{" in CYPHER, label


def test_relationships_reference_declared_variables():
    declared = set()
    for line in CYPHER.splitlines():
        if line.startswith("CREATE (") and ")-[" not in line:
            declared.add(line[len("CREATE (") :].split(":")[0])

    for line in CYPHER.splitlines():
        if ")-[" in line:
            source = line[len("CREATE (") :].split(")")[0]
            target = line.rsplit("->(", 1)[1].rstrip(")")
            assert source in declared, line
            assert target in declared, line


def test_numbers_survive_as_properties():
    assert "value: '28.4 BLEU'" in CYPHER
    assert "baseline: '26.36 BLEU'" in CYPHER


def test_derived_links_are_marked():
    assert "derived: 'true'" in CYPHER


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
    assert variable("concept:self-attn", used) == "concept_self_attn"
    assert variable("concept:self attn", used) == "concept_self_attn_2"
    assert variable("2nd-idea", used) == "n2nd_idea"
    assert variable("!!!", used) == "n"


def test_property_keys_are_identifier_safe():
    # Props come from the digest ("compared to"), so keys need normalising too.
    assert "compared_to:" in CYPHER
    assert "compared to:" not in CYPHER


def test_quotes_inside_literals_are_balanced():
    for line in CYPHER.splitlines():
        if line.startswith("//") or not line:
            continue
        assert line.replace(r"\'", "").count("'") % 2 == 0, line


def test_a_title_is_emitted_as_a_comment():
    assert CYPHER.startswith("// Attention Is All You Need")
