"""Build the bundled demo digest.

The content here is written by hand rather than generated, so that the sample
shipped with the repo is accurate and the app is fully explorable without an
API key. Every number is taken from the paper itself.

Run with: python data/demo/build_demo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.models import Digest  # noqa: E402

OUT = Path(__file__).parent / "attention.json"

DIGEST = {
    "digest_id": "demo-attention",
    "generated_at": "2017-06-12T00:00:00+00:00",
    "model": "demo",
    "truncated": False,
    "word_count": 4800,
    "meta": {
        "title": "Attention Is All You Need",
        "authors": [
            "Ashish Vaswani", "Noam Shazeer", "Niki Parmar", "Jakob Uszkoreit",
            "Llion Jones", "Aidan N. Gomez", "Lukasz Kaiser", "Illia Polosukhin",
        ],
        "year": 2017,
        "venue": "NeurIPS 2017",
        "arxiv_id": "1706.03762",
        "source_url": "https://arxiv.org/abs/1706.03762",
        "abstract": (
            "The dominant sequence transduction models are based on complex recurrent or "
            "convolutional neural networks that include an encoder and a decoder. The best "
            "performing models also connect the encoder and decoder through an attention "
            "mechanism. We propose a new simple network architecture, the Transformer, based "
            "solely on attention mechanisms, dispensing with recurrence and convolutions "
            "entirely."
        ),
    },
    "theme": "Sequence modelling needs attention, not recurrence",
    "tldr": (
        "Throw away recurrence and convolution entirely and build a translation model out of "
        "attention alone — it trains an order of magnitude faster and still beats everything "
        "that came before it."
    ),
    "problem": (
        "Recurrent models read a sentence one word at a time, so the work cannot be spread "
        "across a GPU, and the distance a signal must travel between two related words grows "
        "with how far apart they sit. Long sentences are therefore both slow to train and hard "
        "to get right."
    ),
    "key_idea": (
        "If every position can look directly at every other position in a single step, order "
        "no longer has to be enforced by processing order. It can be supplied as data — a "
        "positional signal added to the input — which frees the whole sequence to be computed "
        "at once."
    ),
    "summary": {
        "eli5": (
            "Older translation programs read a sentence strictly left to right, like someone "
            "reading through a keyhole one word at a time, and had to remember everything they "
            "had seen so far. This paper lets the program look at the whole sentence at once "
            "and decide, for each word, which other words matter to it. Because nothing has to "
            "wait for anything else, a computer can work on every word simultaneously. The "
            "result was both faster to train and better at translating."
        ),
        "overview": (
            "Sequence-to-sequence models had converged on recurrent encoders and decoders with "
            "an attention mechanism bridging them. The authors observe that the recurrence is "
            "doing two jobs — mixing information between positions, and representing word "
            "order — and that attention already does the first job better. So they remove "
            "recurrence entirely. Each layer of the Transformer is self-attention followed by "
            "a small feed-forward network, wrapped in residual connections; word order is "
            "reintroduced as fixed sinusoidal positional encodings added to the embeddings. "
            "Because every position is computed independently, a layer is a couple of large "
            "matrix multiplications rather than a sequential loop, which is exactly the shape "
            "modern accelerators are fast at."
        ),
        "technical": (
            "The Transformer is an encoder-decoder stack, six layers each. A layer applies "
            "multi-head scaled dot-product attention, then a position-wise feed-forward "
            "network, with residual connections and layer normalisation around both. Attention "
            "maps a query against a set of key-value pairs: softmax(QK^T / sqrt(d_k))V, where "
            "the sqrt(d_k) divisor keeps the dot products out of the softmax's saturated "
            "region as dimension grows. Multi-head attention runs h=8 such attentions in "
            "parallel on learned low-dimensional projections and concatenates them, so "
            "different heads can specialise on different relationships — syntactic agreement, "
            "coreference — rather than being forced to average them into one pattern.\n\n"
            "Order is supplied by sinusoidal positional encodings of varying frequency added "
            "to the input embeddings; the authors note learned encodings perform comparably, "
            "and prefer sinusoids on the hypothesis that they extrapolate to longer sequences. "
            "The decoder adds a masked self-attention sub-layer, which blocks each position "
            "from attending to later ones so that training can be parallel while inference "
            "remains autoregressive, plus a cross-attention sub-layer over the encoder output.\n\n"
            "The complexity argument is the heart of the paper. A self-attention layer connects "
            "any two positions in O(1) sequential operations against O(n) for recurrence, at "
            "O(n^2 * d) total cost — favourable whenever sequence length n is smaller than "
            "representation dimension d, which held for the sentence lengths of the day. On "
            "WMT 2014 English-to-German the big model reaches 28.4 BLEU, above the previous "
            "best ensemble at 26.36, after 3.5 days on eight P100 GPUs; the base model trains "
            "in twelve hours. The quadratic cost in sequence length, largely a non-issue at "
            "these lengths, is what later work on long-context models spends its effort on."
        ),
    },
    "contributions": [
        {
            "title": "An architecture with no recurrence or convolution",
            "detail": (
                "The Transformer shows that attention alone is a sufficient mixing mechanism "
                "for sequence transduction, overturning the assumption that sequential "
                "processing was load-bearing."
            ),
            "kind": "method",
        },
        {
            "title": "Multi-head attention",
            "detail": (
                "Running several attention functions in parallel over lower-dimensional "
                "projections lets one layer represent several distinct relationships at once, "
                "instead of averaging them into a single attention distribution."
            ),
            "kind": "method",
        },
        {
            "title": "Scaled dot-product attention",
            "detail": (
                "Dividing by sqrt(d_k) keeps dot products from growing with dimension and "
                "pushing the softmax into regions of vanishing gradient — a one-line fix that "
                "makes dot-product attention trainable at scale."
            ),
            "kind": "method",
        },
        {
            "title": "A complexity argument for attention over recurrence",
            "detail": (
                "A comparison of layer types by computational cost, parallelism, and maximum "
                "path length between positions, which explains why the architecture works "
                "rather than merely showing that it does."
            ),
            "kind": "analysis",
        },
        {
            "title": "State of the art translation at a fraction of the cost",
            "detail": (
                "28.4 BLEU on WMT 2014 English-to-German, beating prior ensembles, for under "
                "a quarter of the training cost of the best previous models."
            ),
            "kind": "empirical",
        },
    ],
    "theme_map": {
        "core": "Attention alone can replace recurrence",
        "nodes": [
            {"id": "transformer", "label": "The Transformer", "kind": "core", "weight": 1.0,
             "blurb": "An encoder-decoder stack built only from attention and feed-forward layers."},
            {"id": "sequential", "label": "Sequential bottleneck", "kind": "problem", "weight": 0.85,
             "blurb": "Recurrent models must process word n before word n+1, so training cannot be parallelised."},
            {"id": "longrange", "label": "Long-range dependencies", "kind": "problem", "weight": 0.75,
             "blurb": "In a recurrent model, a signal between two distant words must survive many intervening steps."},
            {"id": "selfattn", "label": "Self-attention", "kind": "method", "weight": 0.95,
             "blurb": "Every position computes a weighted view of every other position in one step."},
            {"id": "multihead", "label": "Multi-head attention", "kind": "method", "weight": 0.8,
             "blurb": "Eight attention functions run in parallel so one layer can capture several kinds of relationship."},
            {"id": "posenc", "label": "Positional encoding", "kind": "method", "weight": 0.7,
             "blurb": "Sinusoids of different frequencies added to embeddings, so word order survives without recurrence."},
            {"id": "qkv", "label": "Query, key, value", "kind": "concept", "weight": 0.6,
             "blurb": "Each position emits a question, an advertisement, and the content it offers if selected."},
            {"id": "scaling", "label": "Scaling by sqrt(d_k)", "kind": "concept", "weight": 0.45,
             "blurb": "Keeps dot products small enough that the softmax still has usable gradients."},
            {"id": "bleu", "label": "28.4 BLEU on EN-DE", "kind": "evidence", "weight": 0.7,
             "blurb": "Beat the previous best ensemble, which scored 26.36."},
            {"id": "cost", "label": "12 hours to train", "kind": "evidence", "weight": 0.65,
             "blurb": "The base model trains in twelve hours on eight GPUs; earlier models took weeks."},
            {"id": "scale", "label": "Models that scale", "kind": "implication", "weight": 0.8,
             "blurb": "Parallel training is what made the next decade of large language models affordable."},
        ],
        "edges": [
            {"source": "sequential", "target": "transformer", "label": "motivates"},
            {"source": "longrange", "target": "transformer", "label": "motivates"},
            {"source": "transformer", "target": "selfattn", "label": "is built from"},
            {"source": "selfattn", "target": "sequential", "label": "removes"},
            {"source": "selfattn", "target": "longrange", "label": "shortens"},
            {"source": "selfattn", "target": "qkv", "label": "operates on"},
            {"source": "selfattn", "target": "scaling", "label": "stabilised by"},
            {"source": "transformer", "target": "multihead", "label": "stacks"},
            {"source": "multihead", "target": "selfattn", "label": "diversifies"},
            {"source": "transformer", "target": "posenc", "label": "requires"},
            {"source": "posenc", "target": "sequential", "label": "compensates for"},
            {"source": "transformer", "target": "bleu", "label": "achieves"},
            {"source": "transformer", "target": "cost", "label": "achieves"},
            {"source": "cost", "target": "scale", "label": "unlocks"},
        ],
    },
    "method": [
        {
            "id": "embed", "name": "Embed and place",
            "plain": "Turn each token into a vector, then add a positional encoding so the vector also carries where the word sits in the sentence.",
            "why": "Without recurrence nothing else tells the model about order, so order has to arrive as part of the input.",
            "inputs": ["Token ids"], "outputs": ["Position-aware embeddings"],
        },
        {
            "id": "project", "name": "Project to Q, K, V",
            "plain": "From each position's vector, compute three different vectors: a query (what am I looking for), a key (what do I offer), and a value (what I pass on if chosen).",
            "why": "Splitting the roles lets the model learn matching and content separately, instead of comparing raw embeddings.",
            "inputs": ["Position-aware embeddings"], "outputs": ["Queries", "Keys", "Values"],
        },
        {
            "id": "attend", "name": "Scaled dot-product attention",
            "plain": "Score every query against every key, divide by the square root of the key dimension, softmax the scores into weights, and take the weighted sum of values.",
            "why": "This is the step that moves information between positions, and it does it for all pairs at once rather than one hop at a time.",
            "inputs": ["Queries", "Keys", "Values"], "outputs": ["Attended vectors"],
        },
        {
            "id": "heads", "name": "Run eight heads",
            "plain": "Do the whole attention computation eight times over different learned projections, then concatenate the results and mix them with one more linear layer.",
            "why": "One attention distribution has to average all the relationships it cares about. Eight can specialise.",
            "inputs": ["Attended vectors"], "outputs": ["Multi-head output"],
        },
        {
            "id": "ffn", "name": "Position-wise feed-forward",
            "plain": "Push each position's vector through the same small two-layer network, independently of its neighbours.",
            "why": "Attention mixes across positions but is linear in the values; this adds the non-linear processing within a position.",
            "inputs": ["Multi-head output"], "outputs": ["Transformed vectors"],
        },
        {
            "id": "stack", "name": "Residual, normalise, repeat",
            "plain": "Add each sub-layer's input back to its output and layer-normalise, then stack the whole block six times.",
            "why": "Residual connections keep gradients flowing through a deep stack, and depth is where the model's expressiveness comes from.",
            "inputs": ["Transformed vectors"], "outputs": ["Encoder representation"],
        },
        {
            "id": "decode", "name": "Decode with masking",
            "plain": "The decoder attends over its own output so far, but is blocked from seeing future positions, and separately attends over the encoder's output.",
            "why": "The mask lets the whole target sentence be trained in parallel while keeping generation strictly left to right at inference.",
            "inputs": ["Encoder representation", "Target prefix"], "outputs": ["Next-token distribution"],
        },
    ],
    "results": {
        "headline": (
            "The Transformer set a new state of the art on both WMT 2014 translation tasks "
            "while training for a small fraction of the compute previous leaders needed."
        ),
        "metrics": [
            {"name": "BLEU", "dataset": "WMT 2014 English-German", "value": 28.4,
             "baseline": 26.36, "baseline_name": "Previous best ensemble", "unit": "BLEU",
             "higher_is_better": True},
            {"name": "BLEU", "dataset": "WMT 2014 English-French", "value": 41.8,
             "baseline": 41.29, "baseline_name": "Previous best ensemble", "unit": "BLEU",
             "higher_is_better": True},
            {"name": "Training time", "dataset": "Base model, 8 P100 GPUs", "value": 12.0,
             "baseline": None, "baseline_name": None, "unit": "hours",
             "higher_is_better": False},
            {"name": "Training time", "dataset": "Big model, 8 P100 GPUs", "value": 84.0,
             "baseline": None, "baseline_name": None, "unit": "hours",
             "higher_is_better": False},
        ],
        "caveat": (
            "The evidence is machine translation and one English constituency parsing task. "
            "The paper's claim that attention generalises broadly was, at the time, a "
            "conjecture rather than a demonstrated result."
        ),
    },
    "limitations": [
        "Self-attention costs O(n^2) in sequence length. At sentence lengths this is cheap, and the paper treats it as a footnote, but it is the constraint that a decade of later work was built to escape.",
        "Every result is on translation, plus a single parsing experiment. The title's generality outruns the evidence presented.",
        "The claim that sinusoidal encodings extrapolate to longer sequences than those seen in training is stated as a hypothesis and not tested.",
        "Attention weights are offered as interpretable in the appendix figures, but no evaluation supports reading them as explanations.",
        "Results come from a single training run per configuration, with no variance reported across seeds.",
    ],
    "glossary": [
        {"term": "Sequence transduction", "plain": "Turning one sequence into another, such as a sentence in English into a sentence in German."},
        {"term": "Self-attention", "plain": "A layer where every position in a sequence computes a weighted combination of all positions in that same sequence."},
        {"term": "Query, key, value", "plain": "Three vectors derived from each position: what it is looking for, what it advertises, and what it contributes when selected."},
        {"term": "Multi-head attention", "plain": "Several attention computations run in parallel on different learned projections, so one layer can track several kinds of relationship."},
        {"term": "Positional encoding", "plain": "A pattern added to each word's vector that encodes its position, since the architecture has no other sense of order."},
        {"term": "Masked attention", "plain": "Attention with future positions blocked out, so a position can only use what comes before it."},
        {"term": "Residual connection", "plain": "Adding a layer's input to its output, which keeps gradients from vanishing in a deep stack."},
        {"term": "Layer normalisation", "plain": "Rescaling a vector to a standard mean and spread, which keeps training stable."},
        {"term": "BLEU", "plain": "A translation quality score based on overlap with human reference translations. Higher is better."},
        {"term": "Label smoothing", "plain": "Training against slightly softened targets instead of hard ones, which hurts perplexity but improves accuracy and BLEU."},
        {"term": "Beam search", "plain": "Keeping several candidate translations alive during generation instead of committing to the single best next word."},
    ],
    "prereqs": [
        {"concept": "Encoder-decoder models", "why": "The Transformer is one. Its novelty is what replaces the recurrent layers inside, so you need the surrounding shape first.", "level": "essential"},
        {"concept": "Softmax and the dot product", "why": "Attention is a softmax over dot products. Once that sentence is comfortable, section 3.2 is mostly notation.", "level": "essential"},
        {"concept": "Why RNNs are slow to train", "why": "The entire motivation is the sequential dependency in recurrence. Without it the paper reads as an arbitrary redesign.", "level": "essential"},
        {"concept": "Residual networks", "why": "Explains the add-and-normalise pattern wrapped around every sub-layer.", "level": "helpful"},
        {"concept": "BLEU scoring", "why": "Needed only to judge whether the reported gains are large.", "level": "helpful"},
    ],
    "sections": [
        {"heading": "Introduction", "gist": "Frames recurrence as the bottleneck that everything else in the paper is built to remove.",
         "key_points": ["Recurrent models forbid parallelism within a sequence.", "Memory pressure makes long sequences worse.", "Attention had been used alongside recurrence, never instead of it."]},
        {"heading": "Background", "gist": "Positions the work against convolutional alternatives that reduce but do not eliminate the distance problem.",
         "key_points": ["ByteNet and ConvS2S grow path length with distance between positions.", "Self-attention connects any two positions in constant steps.", "Multi-head attention counters the averaging that a single head suffers."]},
        {"heading": "Model Architecture", "gist": "The full specification: attention, multi-head attention, feed-forward layers, and positional encodings.",
         "key_points": ["Six identical layers in both encoder and decoder.", "Scaling by sqrt(d_k) prevents softmax saturation.", "Decoder masking preserves autoregressive generation during parallel training."]},
        {"heading": "Why Self-Attention", "gist": "The argument that makes the paper convincing rather than merely empirical.",
         "key_points": ["Compares layer types on complexity, parallelism and path length.", "Self-attention wins when sequence length is below representation dimension.", "Shorter paths make long-range dependencies easier to learn."]},
        {"heading": "Training", "gist": "The recipe, including the details that turn out to matter as much as the architecture.",
         "key_points": ["Adam with a warmup-then-decay learning rate schedule.", "Residual dropout and label smoothing at 0.1.", "Base model: twelve hours on eight P100 GPUs."]},
        {"heading": "Results", "gist": "New state of the art on both translation tasks, plus ablations isolating each design choice.",
         "key_points": ["28.4 BLEU English-German, 41.8 English-French.", "Ablations show head count and key dimension both matter.", "Constituency parsing tests whether the architecture generalises beyond translation."]},
    ],
    "reading_path": [
        {"order": 1, "target": "Figure 1 (the architecture diagram)", "why": "Everything else is a caption on this picture. Find the encoder, the decoder, and the three places attention appears.", "minutes": 3},
        {"order": 2, "target": "Section 3.2, scaled dot-product and multi-head attention", "why": "The one mechanism the paper introduces. If you read nothing else, read this.", "minutes": 12},
        {"order": 3, "target": "Section 4, Why Self-Attention", "why": "The table comparing path length and parallelism is the actual argument for the design.", "minutes": 8},
        {"order": 4, "target": "Section 3.5, positional encoding", "why": "Answers the obvious objection: with recurrence gone, how does it know word order?", "minutes": 5},
        {"order": 5, "target": "Table 3 (ablations)", "why": "Shows which choices were load-bearing and which were taste.", "minutes": 7},
    ],
    "checks": [
        {"question": "With recurrence removed, how does the model know what order the words came in?",
         "answer": "Positional encodings — sinusoids of varying frequency added directly to the input embeddings. Order becomes part of the data rather than a property of the computation."},
        {"question": "Why divide the attention scores by the square root of the key dimension?",
         "answer": "Dot products grow with dimension. Left unscaled they push the softmax into a flat region where gradients nearly vanish, and training stalls."},
        {"question": "Why use eight attention heads instead of one bigger one?",
         "answer": "A single softmax produces one distribution over positions, so competing relationships get averaged together. Separate heads can each specialise and are concatenated afterwards."},
        {"question": "The decoder is autoregressive, so why can training run in parallel?",
         "answer": "Masking. Each position is blocked from attending to later ones, so the whole target sentence can be processed at once while each position still only ever sees its prefix."},
    ],
}


def build() -> Path:
    digest = Digest.model_validate(DIGEST)
    OUT.write_text(
        json.dumps(digest.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return OUT


if __name__ == "__main__":
    print("wrote", build())
