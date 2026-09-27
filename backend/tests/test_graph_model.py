"""The derived graph has to be faithful to the digest and internally sound."""

import json

import pytest

from app.config import settings
from app.distill import load_demo_digest
from app.graph_model import (
    ARTIFACT,
    CONCEPT,
    METRIC,
    PAPER,
    STEP,
    TERM,
    build_graph,
    mentions,
    rel_type,
    slug,
)
from app.models import Digest

DEMO = load_demo_digest(settings.demo_path)
GRAPH = build_graph(DEMO)


def nodes_of(graph, kind):
    return [n for n in graph.nodes if n.kind == kind]


def test_every_edge_points_at_a_real_node():
    ids = {n.id for n in GRAPH.nodes}
    for edge in GRAPH.edges:
        assert edge.source in ids, edge
        assert edge.target in ids, edge


def test_node_ids_are_unique():
    ids = [n.id for n in GRAPH.nodes]
    assert len(ids) == len(set(ids))


def test_no_self_loops_or_duplicate_edges():
    seen = set()
    for edge in GRAPH.edges:
        assert edge.source != edge.target
        key = (edge.source, edge.target, edge.type)
        assert key not in seen
        seen.add(key)


def test_it_carries_far_more_than_the_theme_map():
    assert len(nodes_of(GRAPH, CONCEPT)) == len(DEMO.theme_map.nodes)
    assert len(GRAPH.nodes) > len(DEMO.theme_map.nodes) * 3
    assert {PAPER, CONCEPT, STEP, ARTIFACT, METRIC} <= set(GRAPH.counts)


def test_the_method_forms_a_connected_chain():
    steps = sorted(nodes_of(GRAPH, STEP), key=lambda n: int(n.props["order"]))
    assert [s.props["order"] for s in steps] == [str(i + 1) for i in range(len(DEMO.method))]

    then = {(e.source, e.target) for e in GRAPH.edges if e.type == "THEN"}
    for earlier, later in zip(steps, steps[1:], strict=False):
        assert (earlier.id, later.id) in then


def test_shared_artifacts_join_consecutive_stages():
    # "Queries" is produced by one stage and consumed by the next; that must be
    # one node, which is what makes the method a graph rather than a list.
    queries = next(n for n in nodes_of(GRAPH, ARTIFACT) if n.label == "Queries")
    produced = [e for e in GRAPH.edges if e.target == queries.id and e.type == "PRODUCES"]
    fed = [e for e in GRAPH.edges if e.source == queries.id and e.type == "FEEDS"]
    assert produced and fed
    assert produced[0].source != fed[0].target


def test_metrics_keep_their_numbers_and_baselines():
    bleu = next(
        n for n in nodes_of(GRAPH, METRIC) if "English-German" in n.props.get("dataset", "")
    )
    assert bleu.props["value"] == "28.4 BLEU"
    assert bleu.props["baseline"] == "26.36 BLEU"
    assert bleu.props["direction"] == "higher is better"


def test_derived_term_links_are_flagged_as_derived():
    derived = [e for e in GRAPH.edges if e.derived]
    assert derived, "the glossary should connect to where its terms are used"
    assert all(e.source.startswith("term:") for e in derived)
    assert all(e.type == "APPEARS_IN" for e in derived)


def test_busy_labels_start_hidden():
    assert TERM in GRAPH.quiet
    assert CONCEPT not in GRAPH.quiet


def test_degrees_match_the_edges():
    for node in GRAPH.nodes:
        touching = sum(
            1 for e in GRAPH.edges if e.source == node.id or e.target == node.id
        )
        assert node.degree == touching, node.label


def test_building_is_deterministic():
    again = build_graph(load_demo_digest(settings.demo_path))
    assert [n.id for n in again.nodes] == [n.id for n in GRAPH.nodes]
    assert [(e.source, e.target, e.type) for e in again.edges] == [
        (e.source, e.target, e.type) for e in GRAPH.edges
    ]


def test_insights_are_present_and_specific():
    headlines = [i.headline for i in GRAPH.insights]
    assert any("holds the paper together" in h for h in headlines)
    assert any("nodes," in h for h in headlines)


def test_evidence_gap_only_fires_when_a_claim_is_really_unreachable():
    # Every concept in the demo sits within a few hops of a metric, so the
    # warning must stay quiet rather than firing on all of them.
    assert not any(i.kind == "evidence-gap" for i in GRAPH.insights)


def test_evidence_gap_fires_when_a_claim_is_stranded():
    payload = json.loads(settings.demo_path.read_text())
    payload["theme_map"]["nodes"].append(
        {
            "id": "island",
            "label": "Unbacked claim",
            "kind": "implication",
            "weight": 0.5,
            "blurb": "Nothing measures this.",
        }
    )
    graph = build_graph(Digest.model_validate(payload))
    gap = next(i for i in graph.insights if i.kind == "evidence-gap")
    assert "Unbacked claim" in gap.detail


def test_orphan_insight_ignores_unmatched_glossary_terms():
    # A term the matcher did not place is a limit of the matcher, not a flaw in
    # the paper, so it must not be reported as one.
    orphans = [i for i in GRAPH.insights if i.kind == "orphans"]
    for insight in orphans:
        for term in nodes_of(GRAPH, TERM):
            assert term.label not in insight.detail


def test_a_digest_with_no_method_or_metrics_still_builds():
    payload = json.loads(settings.demo_path.read_text())
    payload["method"] = []
    payload["results"]["metrics"] = []
    graph = build_graph(Digest.model_validate(payload))
    assert nodes_of(graph, PAPER)
    assert not nodes_of(graph, STEP)
    assert not nodes_of(graph, ARTIFACT)
    ids = {n.id for n in graph.nodes}
    assert all(e.source in ids and e.target in ids for e in graph.edges)


@pytest.mark.parametrize(
    "needle,haystack,expected",
    [
        ("attention", "Self-attention over the sequence", True),
        ("BLEU", "scored 28.4 BLEU overall", True),
        ("key", "monkeys are not keys", False),   # whole words only
        ("qkv", "the qkv projection", False),     # too short to be safe
    ],
)
def test_mention_matching(needle, haystack, expected):
    assert mentions(needle, haystack) is expected


@pytest.mark.parametrize(
    "raw,expected", [("Self-Attention", "self_attention"), ("  ", "x"), ("Q, K, V", "q_k_v")]
)
def test_slug(raw, expected):
    assert slug(raw) == expected


def test_rel_type_is_a_valid_identifier():
    assert rel_type("is built from") == "IS_BUILT_FROM"
    assert rel_type("") == "RELATED_TO"
