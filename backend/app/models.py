"""The shape of an understood paper.

Everything downstream — the LLM tool schema, the cache, the API and the UI —
is derived from these models, so this file is the single source of truth for
what PaperPrism means by "understanding a paper".
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NodeKind = Literal["core", "problem", "method", "concept", "evidence", "implication"]
ContribKind = Literal["method", "theory", "dataset", "empirical", "system", "analysis"]


# --------------------------------------------------------------------------
# Visual layer: the theme map
# --------------------------------------------------------------------------


class ConceptNode(BaseModel):
    """One idea in the paper, placed on the theme map."""

    id: str = Field(description="Short slug, unique within the map, e.g. 'self_attn'.")
    label: str = Field(description="Two to four words. This is drawn inside the node.")
    kind: NodeKind = Field(
        description=(
            "'core' for the single central idea (exactly one node uses it), "
            "'problem' for what was broken before, 'method' for machinery the paper "
            "introduces, 'concept' for supporting ideas, 'evidence' for results that "
            "back the claim, 'implication' for what it unlocks."
        )
    )
    weight: float = Field(
        ge=0.0, le=1.0, description="How central this is to the paper. Drives node size."
    )
    blurb: str = Field(
        description="One sentence, plain language, shown when the node is opened."
    )


class ConceptEdge(BaseModel):
    """A labelled relationship between two nodes."""

    source: str = Field(description="id of the originating node")
    target: str = Field(description="id of the destination node")
    label: str = Field(
        description="The relationship in one to three words, e.g. 'replaces', 'enables'."
    )


class ThemeMap(BaseModel):
    """The main visual: the paper's argument as a labelled graph."""

    core: str = Field(
        description="The paper's central theme in at most ten words. Drawn at the centre."
    )
    nodes: list[ConceptNode] = Field(
        min_length=5,
        max_length=14,
        description="5-14 nodes. Exactly one must have kind 'core'.",
    )
    edges: list[ConceptEdge] = Field(
        description=(
            "Every non-core node must be reachable from the core node. "
            "Prefer a readable map over an exhaustive one."
        )
    )


# --------------------------------------------------------------------------
# Visual layer: the method pipeline
# --------------------------------------------------------------------------


class MethodStep(BaseModel):
    """One stage of what the paper actually does, in execution order."""

    id: str
    name: str = Field(description="Two to five words naming the stage.")
    plain: str = Field(description="What happens here, in language a smart non-expert follows.")
    why: str = Field(description="Why this step is needed at all. The reason it exists.")
    inputs: list[str] = Field(description="What goes in, named concretely.")
    outputs: list[str] = Field(description="What comes out.")


# --------------------------------------------------------------------------
# Visual layer: results
# --------------------------------------------------------------------------


class Metric(BaseModel):
    """A single headline number, with the number it is meant to beat."""

    name: str = Field(description="What is measured, e.g. 'BLEU', 'Top-1 accuracy'.")
    dataset: str | None = Field(default=None, description="What it was measured on.")
    value: float = Field(description="The paper's result.")
    baseline: float | None = Field(
        default=None, description="The number being compared against, if the paper gives one."
    )
    baseline_name: str | None = Field(default=None, description="Whose number the baseline is.")
    unit: str | None = Field(default=None, description="e.g. '%', 'ms', 'BLEU'. Omit if unitless.")
    higher_is_better: bool = True


class Results(BaseModel):
    headline: str = Field(description="One sentence: what the numbers actually establish.")
    metrics: list[Metric] = Field(
        max_length=8, description="Up to 8 metrics that carry the paper's claim. Fewer is fine."
    )
    caveat: str | None = Field(
        default=None,
        description=(
            "What the numbers do NOT show, if the paper's evidence is narrower "
            "than its claim."
        ),
    )


# --------------------------------------------------------------------------
# Text layer
# --------------------------------------------------------------------------


class LayeredSummary(BaseModel):
    """The same paper at three depths. Each level must stand alone."""

    eli5: str = Field(
        description=(
            "2-4 sentences, no jargon at all, no equations. An analogy is welcome. "
            "A curious teenager should finish this knowing what the paper is for."
        )
    )
    overview: str = Field(
        description=(
            "One paragraph for someone in an adjacent field: the problem, the move the "
            "paper makes, and why it works. Technical terms allowed if immediately unpacked."
        )
    )
    technical: str = Field(
        description=(
            "2-3 paragraphs for a practitioner: the actual mechanism, the setup, the "
            "evidence, and the honest limits. Assume the reader knows the field's basics."
        )
    )


class Contribution(BaseModel):
    title: str = Field(description="The contribution in under ten words.")
    detail: str = Field(description="One or two sentences on what it is and why it matters.")
    kind: ContribKind


class GlossaryItem(BaseModel):
    term: str = Field(description="A term the paper uses that a newcomer would stumble on.")
    plain: str = Field(
        description="A one-sentence plain-English definition, in this paper's context."
    )


class Prereq(BaseModel):
    concept: str
    why: str = Field(description="What part of the paper becomes readable once you know this.")
    level: Literal["essential", "helpful"]


class SectionDigest(BaseModel):
    heading: str
    gist: str = Field(
        description="One sentence on what this section does for the paper's argument."
    )
    key_points: list[str] = Field(max_length=5)


class ReadingHop(BaseModel):
    """A route through the paper for someone who will not read it front to back."""

    order: int
    target: str = Field(description="Section heading, figure or table to read.")
    why: str = Field(description="What you get from it.")
    minutes: int = Field(ge=1, le=60)


class Check(BaseModel):
    """A question that reveals whether the reader actually followed the paper."""

    question: str
    answer: str


# --------------------------------------------------------------------------
# The whole thing
# --------------------------------------------------------------------------


class DigestCore(BaseModel):
    """The part of a digest the model is asked to produce.

    Bibliographic fields live on `Digest` instead, because we get those from
    the source metadata rather than from the model.
    """

    theme: str = Field(description="The paper's main theme in at most ten words. No hedging.")
    tldr: str = Field(description="One sentence a reader could repeat to a colleague.")
    problem: str = Field(description="What was wrong or missing before this paper.")
    key_idea: str = Field(description="The single move that makes the paper work.")
    summary: LayeredSummary
    contributions: list[Contribution] = Field(min_length=1, max_length=6)
    theme_map: ThemeMap
    method: list[MethodStep] = Field(
        max_length=8, description="The paper's approach as ordered stages. Empty if not applicable."
    )
    results: Results
    limitations: list[str] = Field(
        max_length=6,
        description="Honest limits. Include ones the paper downplays, marked as such.",
    )
    glossary: list[GlossaryItem] = Field(max_length=14)
    prereqs: list[Prereq] = Field(max_length=6)
    sections: list[SectionDigest] = Field(max_length=14)
    reading_path: list[ReadingHop] = Field(max_length=6)
    checks: list[Check] = Field(max_length=4)


class PaperMeta(BaseModel):
    title: str = "Untitled paper"
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    arxiv_id: str | None = None
    source_url: str | None = None
    abstract: str | None = None


class Digest(DigestCore):
    """A fully assembled digest, as served to the frontend."""

    meta: PaperMeta
    digest_id: str
    generated_at: str
    model: str = Field(description="Which model produced this, or 'demo' for the bundled sample.")
    truncated: bool = Field(
        default=False, description="True if the paper was too long to send in full."
    )
    word_count: int = 0
