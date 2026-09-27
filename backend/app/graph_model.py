"""Expand a digest into the whole paper as one property graph.

The theme map is only the argument's skeleton. A digest also knows the method's
stages and what each one consumes and produces, the numbers and what they are
measured against, the contributions, the limitations, the vocabulary and the
sections. Those are all connections a reader would otherwise have to hold in
their head.

This module derives the full graph from a digest that already exists. It costs
no model call, runs on anything already cached, and is deterministic, so the
same digest always yields the same graph.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict

from pydantic import BaseModel, Field

from .models import Digest

# Node labels, in the order the UI shows them.
PAPER = "Paper"
CONCEPT = "Concept"
STEP = "Step"
ARTIFACT = "Artifact"
METRIC = "Metric"
CONTRIBUTION = "Contribution"
LIMITATION = "Limitation"
TERM = "Term"
PREREQ = "Prereq"
SECTION = "Section"

LABEL_ORDER = (
    PAPER, CONCEPT, STEP, ARTIFACT, METRIC,
    CONTRIBUTION, LIMITATION, TERM, PREREQ, SECTION,
)

# Labels that would swamp the first look; the reader turns them on.
QUIET_BY_DEFAULT = (TERM, SECTION, PREREQ)

# A term shorter than this matches too much to be worth linking.
MIN_TERM_CHARS = 4


class GraphNode(BaseModel):
    id: str
    label: str
    kind: str
    blurb: str = ""
    weight: float = 0.5
    degree: int = 0
    props: dict[str, str] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    type: str
    label: str
    derived: bool = Field(
        default=False,
        description="True when inferred from text rather than stated by the digest.",
    )


class Insight(BaseModel):
    kind: str
    headline: str
    detail: str


class PaperGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    insights: list[Insight]
    counts: dict[str, int]
    quiet: list[str] = Field(
        description="Labels the UI should start with hidden, to avoid a hairball."
    )


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

_SLUG = re.compile(r"[^a-z0-9]+")


def slug(text: str, fallback: str = "x") -> str:
    out = _SLUG.sub("_", text.lower()).strip("_")
    return out or fallback


def rel_type(label: str) -> str:
    out = re.sub(r"\W+", "_", label).strip("_").upper()
    return re.sub(r"^(?=\d)", "R", out) or "RELATED_TO"


def mentions(needle: str, haystack: str) -> bool:
    """Whole-word, case-insensitive containment."""
    if len(needle) < MIN_TERM_CHARS:
        return False
    return re.search(rf"\b{re.escape(needle)}\b", haystack, re.IGNORECASE) is not None


class _Builder:
    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        self._seen_edges: set[tuple[str, str, str]] = set()

    def node(self, node: GraphNode) -> str:
        # First definition wins, so a later weaker mention cannot overwrite it.
        self.nodes.setdefault(node.id, node)
        return node.id

    def edge(
        self, source: str, target: str, type_: str, label: str, *, derived: bool = False
    ) -> None:
        if source == target:
            return
        if source not in self.nodes or target not in self.nodes:
            return
        key = (source, target, type_)
        if key in self._seen_edges:
            return
        self._seen_edges.add(key)
        self.edges.append(
            GraphEdge(source=source, target=target, type=type_, label=label, derived=derived)
        )


# --------------------------------------------------------------------------
# Construction
# --------------------------------------------------------------------------


def build_graph(digest: Digest) -> PaperGraph:
    builder = _Builder()

    paper_id = "paper"
    builder.node(
        GraphNode(
            id=paper_id,
            label=digest.meta.title,
            kind=PAPER,
            blurb=digest.tldr,
            weight=1.0,
            props={
                "theme": digest.theme,
                **({"year": str(digest.meta.year)} if digest.meta.year else {}),
                **({"venue": digest.meta.venue} if digest.meta.venue else {}),
            },
        )
    )

    _add_concepts(builder, digest, paper_id)
    _add_method(builder, digest)
    _add_metrics(builder, digest, paper_id)
    _add_contributions(builder, digest, paper_id)
    _add_limitations(builder, digest, paper_id)
    _add_prereqs(builder, digest, paper_id)
    _add_sections(builder, digest, paper_id)
    _link_terms(builder, digest)

    nodes = list(builder.nodes.values())
    _score(nodes, builder.edges)

    counts = Counter(node.kind for node in nodes)
    return PaperGraph(
        nodes=nodes,
        edges=builder.edges,
        insights=_insights(nodes, builder.edges),
        counts={label: counts.get(label, 0) for label in LABEL_ORDER if counts.get(label)},
        quiet=[label for label in QUIET_BY_DEFAULT if counts.get(label)],
    )


def _add_concepts(builder: _Builder, digest: Digest, paper_id: str) -> None:
    core_id: str | None = None
    for node in digest.theme_map.nodes:
        node_id = f"concept:{node.id}"
        builder.node(
            GraphNode(
                id=node_id,
                label=node.label,
                kind=CONCEPT,
                blurb=node.blurb,
                weight=node.weight,
                props={"role": node.kind},
            )
        )
        if node.kind == "core":
            core_id = node_id

    for edge in digest.theme_map.edges:
        builder.edge(
            f"concept:{edge.source}",
            f"concept:{edge.target}",
            rel_type(edge.label),
            edge.label,
        )

    if core_id:
        builder.edge(paper_id, core_id, "CLAIMS", "claims")


def _add_method(builder: _Builder, digest: Digest) -> None:
    """The method as a pipeline, joined through what each stage passes on.

    Naming an input the same as an earlier output is the paper telling you the
    stages are connected; turning both into one Artifact node makes that
    visible instead of leaving it as a coincidence of wording.
    """
    step_ids: list[str] = []

    for index, step in enumerate(digest.method):
        step_id = f"step:{slug(step.id or step.name, f's{index}')}"
        builder.node(
            GraphNode(
                id=step_id,
                label=step.name,
                kind=STEP,
                blurb=step.plain,
                weight=0.6,
                props={"order": str(index + 1), "why": step.why},
            )
        )
        step_ids.append(step_id)

    for earlier, later in zip(step_ids, step_ids[1:], strict=False):
        builder.edge(earlier, later, "THEN", "then")

    for step_id, step in zip(step_ids, digest.method, strict=True):
        for name in step.outputs:
            artifact = _artifact(builder, name)
            builder.edge(step_id, artifact, "PRODUCES", "produces")
        for name in step.inputs:
            artifact = _artifact(builder, name)
            builder.edge(artifact, step_id, "FEEDS", "feeds")


def _artifact(builder: _Builder, name: str) -> str:
    """Identity is the normalised name, so the same thing is one node."""
    artifact_id = f"artifact:{slug(name)}"
    builder.node(
        GraphNode(id=artifact_id, label=name, kind=ARTIFACT, blurb="", weight=0.35)
    )
    return artifact_id


def _add_metrics(builder: _Builder, digest: Digest, paper_id: str) -> None:
    core = next(
        (f"concept:{n.id}" for n in digest.theme_map.nodes if n.kind == "core"), None
    )

    for index, metric in enumerate(digest.results.metrics):
        parts = [metric.name]
        if metric.dataset:
            parts.append(metric.dataset)
        metric_id = f"metric:{slug('_'.join(parts), f'm{index}')}"

        value = f"{metric.value:g}{f' {metric.unit}' if metric.unit else ''}"
        props = {
            "value": value,
            "direction": "higher is better" if metric.higher_is_better else "lower is better",
        }
        if metric.dataset:
            props["dataset"] = metric.dataset
        if metric.baseline is not None:
            props["baseline"] = (
                f"{metric.baseline:g}{f' {metric.unit}' if metric.unit else ''}"
            )
            if metric.baseline_name:
                props["compared to"] = metric.baseline_name

        builder.node(
            GraphNode(
                id=metric_id,
                label=f"{metric.name} {value}",
                kind=METRIC,
                blurb=f"{metric.name} on {metric.dataset}" if metric.dataset else metric.name,
                weight=0.55,
                props=props,
            )
        )
        builder.edge(paper_id, metric_id, "REPORTS", "reports")
        if core:
            builder.edge(metric_id, core, "SUPPORTS", "supports")


def _add_contributions(builder: _Builder, digest: Digest, paper_id: str) -> None:
    for index, contribution in enumerate(digest.contributions):
        node_id = f"contribution:{slug(contribution.title, f'c{index}')}"
        builder.node(
            GraphNode(
                id=node_id,
                label=contribution.title,
                kind=CONTRIBUTION,
                blurb=contribution.detail,
                weight=0.6,
                props={"type": contribution.kind},
            )
        )
        builder.edge(paper_id, node_id, "CONTRIBUTES", "contributes")


def _add_limitations(builder: _Builder, digest: Digest, paper_id: str) -> None:
    for index, limitation in enumerate(digest.limitations):
        node_id = f"limitation:{index}"
        # The whole limitation is the blurb; the caption is a readable stub.
        caption = limitation.split(".")[0][:60]
        builder.node(
            GraphNode(
                id=node_id,
                label=caption,
                kind=LIMITATION,
                blurb=limitation,
                weight=0.4,
            )
        )
        builder.edge(paper_id, node_id, "LIMITED_BY", "limited by")


def _add_prereqs(builder: _Builder, digest: Digest, paper_id: str) -> None:
    for index, prereq in enumerate(digest.prereqs):
        node_id = f"prereq:{slug(prereq.concept, f'p{index}')}"
        builder.node(
            GraphNode(
                id=node_id,
                label=prereq.concept,
                kind=PREREQ,
                blurb=prereq.why,
                weight=0.5 if prereq.level == "essential" else 0.35,
                props={"level": prereq.level},
            )
        )
        builder.edge(node_id, paper_id, "ASSUMED_BY", "assumed by")


def _add_sections(builder: _Builder, digest: Digest, paper_id: str) -> None:
    for index, section in enumerate(digest.sections):
        node_id = f"section:{slug(section.heading, f's{index}')}"
        builder.node(
            GraphNode(
                id=node_id,
                label=section.heading,
                kind=SECTION,
                blurb=section.gist,
                weight=0.4,
                props={"order": str(index + 1)},
            )
        )
        builder.edge(paper_id, node_id, "HAS_SECTION", "has section")


def _link_terms(builder: _Builder, digest: Digest) -> None:
    """Connect vocabulary to wherever it is actually used.

    These links are inferred from wording rather than stated by the digest, so
    they are flagged as derived and drawn differently. They are what turns a
    list of definitions into part of the graph: a term that surfaces in four
    stages is doing real work in the paper.
    """
    targets: list[tuple[str, str]] = []
    for node in builder.nodes.values():
        if node.kind in (CONCEPT, STEP, SECTION, CONTRIBUTION):
            targets.append((node.id, f"{node.label} {node.blurb} {' '.join(node.props.values())}"))

    for item in digest.glossary:
        term_id = f"term:{slug(item.term)}"
        builder.node(
            GraphNode(
                id=term_id,
                label=item.term,
                kind=TERM,
                blurb=item.plain,
                weight=0.3,
            )
        )
        for target_id, text in targets:
            if mentions(item.term, text):
                builder.edge(term_id, target_id, "APPEARS_IN", "appears in", derived=True)


# --------------------------------------------------------------------------
# Scoring and insights
# --------------------------------------------------------------------------


def _score(nodes: list[GraphNode], edges: list[GraphEdge]) -> None:
    degree: Counter[str] = Counter()
    for edge in edges:
        degree[edge.source] += 1
        degree[edge.target] += 1

    busiest = max(degree.values(), default=1) or 1
    for node in nodes:
        node.degree = degree.get(node.id, 0)
        if node.kind in (ARTIFACT, TERM, SECTION, LIMITATION):
            # These have no stated importance, so connectedness stands in.
            node.weight = 0.25 + 0.55 * (node.degree / busiest)


def _within(
    nodes: list[GraphNode], edges: list[GraphEdge], seeds: set[str], hops: int
) -> set[str]:
    """Every node reachable from `seeds` within `hops`, ignoring direction."""
    if not seeds:
        return set()
    neighbours: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        neighbours[edge.source].add(edge.target)
        neighbours[edge.target].add(edge.source)

    reached = set(seeds)
    frontier = set(seeds)
    for _ in range(hops):
        nxt: set[str] = set()
        for node_id in frontier:
            nxt |= neighbours[node_id] - reached
        if not nxt:
            break
        reached |= nxt
        frontier = nxt
    return reached


def _insights(nodes: list[GraphNode], edges: list[GraphEdge]) -> list[Insight]:
    """Things worth noticing that are visible in the graph but not in the text."""
    insights: list[Insight] = []

    ranked = sorted(
        (n for n in nodes if n.kind not in (PAPER, SECTION)),
        key=lambda n: (-n.degree, n.id),
    )
    if ranked and ranked[0].degree > 1:
        hub = ranked[0]
        insights.append(
            Insight(
                kind="hub",
                headline=f"{hub.label} holds the paper together",
                detail=(
                    f"It takes part in {hub.degree} relationships, more than anything "
                    "else here. If one idea is worth understanding first, it is this one."
                ),
            )
        )

    # An artifact several stages touch is where the method's data actually flows.
    artifacts = [n for n in nodes if n.kind == ARTIFACT and n.degree >= 3]
    if artifacts:
        busiest = max(artifacts, key=lambda n: (n.degree, n.id))
        insights.append(
            Insight(
                kind="pipeline",
                headline=f"Everything passes through {busiest.label}",
                detail=(
                    f"{busiest.degree} stages of the method produce or consume it, so it "
                    "is the method's load-bearing intermediate."
                ),
            )
        )

    spread = [n for n in nodes if n.kind == TERM and n.degree >= 3]
    if spread:
        widest = max(spread, key=lambda n: (n.degree, n.id))
        insights.append(
            Insight(
                kind="vocabulary",
                headline=f"'{widest.label}' runs through the whole paper",
                detail=(
                    f"It turns up in {widest.degree} different places. Terms that spread "
                    "this widely are usually the ones worth pinning down first."
                ),
            )
        )

    # A claim with nothing measuring it is what a sceptical reader wants to see.
    # Support is reachability, not a direct edge: metrics attach to the central
    # claim, so requiring a direct link would mark every other concept
    # unsupported and say nothing at all.
    unsupported = [
        n
        for n in nodes
        if n.kind == CONCEPT
        and n.props.get("role") in ("method", "implication")
        and n.id not in _within(nodes, edges, {n.id for n in nodes if n.kind == METRIC}, 3)
    ]
    if unsupported and any(n.kind == METRIC for n in nodes):
        names = ", ".join(n.label for n in unsupported[:3])
        insights.append(
            Insight(
                kind="evidence-gap",
                headline="Not every claim has a number behind it",
                detail=(
                    f"{names} connect to no reported metric. That may be fine, but it is "
                    "where the paper is asking for trust rather than showing evidence."
                ),
            )
        )

    # Terms are linked by matching wording, so an unlinked one may just be a
    # miss by the matcher. Blaming the paper for that would be wrong.
    lonely = [n for n in nodes if n.degree == 0 and n.kind not in (PAPER, TERM)]
    if lonely:
        insights.append(
            Insight(
                kind="orphans",
                headline=f"{len(lonely)} item{'s' if len(lonely) > 1 else ''} stand alone",
                detail=(
                    "Nothing in the digest connects to "
                    + ", ".join(n.label for n in lonely[:3])
                    + ". Usually a sign the paper mentions it without following through."
                ),
            )
        )

    derived = sum(1 for edge in edges if edge.derived)
    insights.append(
        Insight(
            kind="scale",
            headline=f"{len(nodes)} nodes, {len(edges)} relationships",
            detail=(
                f"{len(edges) - derived} are stated by the digest; {derived} were inferred "
                "from where the paper's own vocabulary reappears."
                if derived
                else "Every relationship here is one the digest states outright."
            ),
        )
    )

    return insights
