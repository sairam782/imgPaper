"""Regenerate the synthetic paper PDF used by the ingest tests.

Run with: python tests/make_fixture.py
Requires reportlab, which is a dev-only convenience and not a project dependency.
"""

from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

OUT = Path(__file__).parent / "fixtures" / "sample_paper.pdf"

BODY = getSampleStyleSheet()["BodyText"]
TITLE = ParagraphStyle("t", parent=BODY, fontSize=16, leading=20, spaceAfter=12)
HEAD = ParagraphStyle("h", parent=BODY, fontSize=12, leading=15, spaceBefore=12, spaceAfter=6)

LOREM = (
    "We describe the construction in detail and analyse its behaviour under the "
    "assumptions stated above. The resulting procedure is straightforward to "
    "implement and requires no changes to the surrounding training pipeline. "
    "Throughout, we write n for the number of examples and d for the embedding "
    "dimension. "
) * 4

CONTENT = [
    (TITLE, "Sparse Routing Improves Sample Efficiency in Small Language Models"),
    (BODY, "Ada Okonkwo, Rune Halvorsen, Priya Raghavan"),
    (BODY, "Institute for Applied Learning Systems"),
    (HEAD, "Abstract"),
    (
        BODY,
        "Small language models are usually trained densely, which wastes capacity on "
        "tokens that need very little computation. We introduce sparse routing, a "
        "mechanism that sends each token to one of k lightweight expert blocks chosen "
        "by a learned router. On three benchmarks, sparse routing matches dense "
        "baselines with 41 percent fewer training tokens.",
    ),
    (HEAD, "1 Introduction"),
    (BODY, "Dense training treats every token as equally expensive. " + LOREM),
    (HEAD, "2 Related Work"),
    (BODY, "Mixture-of-experts models have a long history. " + LOREM),
    (HEAD, "3 Method"),
    (BODY, "Our method has three parts: a router, a set of experts, and a load term. " + LOREM),
    (HEAD, "3.1 The Router"),
    (BODY, "The router is a single linear layer followed by a softmax over k experts. " + LOREM),
    (HEAD, "3.2 Load Balancing"),
    (BODY, "Without a balancing term the router collapses onto one expert. " + LOREM),
    (HEAD, "4 Experiments"),
    (BODY, "We evaluate on WikiText-103, C4 and a held-out code corpus. " + LOREM),
    (HEAD, "5 Results"),
    (
        BODY,
        "Sparse routing reaches a perplexity of 18.4 on WikiText-103 against a dense "
        "baseline of 18.6, while using 41 percent fewer training tokens. " + LOREM,
    ),
    (HEAD, "6 Limitations"),
    (BODY, "Our experiments are limited to models below one billion parameters. " + LOREM),
    (HEAD, "7 Conclusion"),
    (BODY, "Sparse routing is a cheap way to buy sample efficiency. " + LOREM),
    (HEAD, "References"),
    (BODY, "[1] Shazeer et al. Outrageously large neural networks. ICLR 2017."),
    (BODY, "[2] Fedus et al. Switch Transformers. JMLR 2022."),
]


def build() -> Path:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=LETTER, title="Sparse Routing")
    flow = []
    for style, text in CONTENT:
        flow.append(Paragraph(text, style))
        flow.append(Spacer(1, 4))
    doc.build(flow)
    return OUT


if __name__ == "__main__":
    print("wrote", build())
