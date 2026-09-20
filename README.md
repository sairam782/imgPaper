# PaperPrism

Research papers are written to be defensible, not to be understood. PaperPrism
takes a paper and refracts it into the things that actually make it land: a map
of its argument, its method drawn as a pipeline, its evidence charted against
the baselines it claims to beat, and a summary that scales from "explain it
simply" to the full technical account.

Paste an arXiv link, upload a PDF, or drop in the text.

---

## What you get

**A theme map.** The paper's argument as a labelled graph: the core claim in the
centre, what was broken on the left, the machinery across the top, supporting
ideas on the right, evidence and consequences along the bottom. Every edge is a
real relationship — *self-attention* **removes** *sequential bottleneck* — not a
vague line between related things. Hover anything to see what it means and what
it connects to.

**A summary at three depths.** The same paper written three times: no jargon at
all, then for a researcher in an adjacent field, then for someone who might
build on the work. Each level stands alone; the shallow one is not a truncation
of the deep one.

**The method as a pipeline.** Ordered stages you can step through, each with
what it does, what goes in and out, and — the part papers usually leave implicit
— why that step exists at all.

**Evidence, charted honestly.** Headline numbers against their baselines, scaled
against each other rather than against zero so a two percent gain is not drawn
as a doubling. Metrics the paper reports without a comparison get no bar, because
a lone full-width bar is a claim the authors did not make.

**The parts that get skipped.** Limitations including the ones the paper moves
past quickly, prerequisites with a reason attached, a jargon glossary in this
paper's context rather than a dictionary's, a reading route for people who will
not read it front to back, and a few questions that reveal whether it landed.

## Try it without an API key

The repo ships a complete, hand-checked digest of *Attention Is All You Need*.
Start the server and click **See a finished example** — every part of the
interface works against it, no key needed.

## Run it locally

```bash
./run.sh
```

That is the whole thing. It creates the virtualenv, installs both halves,
builds the frontend and starts the server on <http://localhost:8000>. Re-running
it skips whatever is already done, and rebuilds the frontend only when the
source has changed.

To analyse real papers, add your key:

```bash
cp .env.example .env
# open .env and set ANTHROPIC_API_KEY=sk-ant-...
./run.sh
```

The header shows which model is in use, or `demo mode` when no key is set.
A key that the API rejects produces a message saying exactly that, rather than
a generic failure.

Other options: `./run.sh 9000` picks a port, `./run.sh --rebuild` forces a fresh
frontend build.

**Keep the key out of the repo.** `.env` is gitignored; do not move the key into
`.env.example`, any source file, or a commit.

### Working on it

`make dev` runs the API with reload on `:8000` and the Vite dev server on
`:5173`, which proxies `/api` to the backend.

| command | what it does |
| --- | --- |
| `./run.sh` | install what is missing, build, and serve on :8000 |
| `make dev` | API with reload, plus the Vite dev server |
| `make test` | the backend test suite |
| `make lint` | ruff on the backend, `tsc --noEmit` on the frontend |
| `make demo` | rebuild the bundled demo digest from its source |

### Configuration

Settings come from the environment, and `.env` is read at startup. A real
environment variable always beats the file, so `PAPERPRISM_MODEL=claude-opus-5
./run.sh` works for a one-off. See `.env.example` for every option.

## How it works

```
arXiv id / PDF / pasted text
  ↓  ingest      fetch metadata, extract text, rebuild sections, drop references
  ↓  condense    only for long papers: shrink each section, preserving its numbers
  ↓  distill     one forced tool call against a strict schema, with a corrective retry
  ↓  cache       content-addressed, so the same paper is instant the second time
  ↓  render      theme map, method pipeline, evidence charts, layered summary
```

**Ingest.** PDF text extraction loses structure, so `sectionize.py` rebuilds it:
numbered and unnumbered headings, hyphenated line breaks rejoined, titles
reassembled from the lines they wrapped across, references cut off the end.
The model receives a paper, not a blob.

**Condensation.** Papers over the threshold are condensed section by section
first, by a cheaper model told to preserve every numeric result exactly. This
is why a forty-page paper does not lose everything after page eight.

**Distillation.** One call, with `tool_choice` forcing a schema derived from the
Pydantic models in `backend/app/models.py`. If the result fails validation the
model gets one corrective round with the exact errors, which fixes nearly every
schema miss. If it fails twice, the request errors rather than returning
something half-built.

**Progress.** Analysis takes tens of seconds, so requests become jobs that
publish stage updates over server-sent events. The UI shows what is actually
happening rather than an indefinite spinner.

### The schema is the product

`backend/app/models.py` is the single source of truth. It defines the digest,
generates the tool schema the model must fill, validates what comes back, and
mirrors into `frontend/src/types.ts`. The field descriptions in it are not
documentation — they are the instructions the model reads. Changing what
"understanding a paper" means starts there.

## On accuracy

The model is told, in the strongest terms the prompt can manage, never to invent
a number: every value in `results.metrics` must appear in the text it was given,
and an empty list is a correct answer where a plausible fabricated one is not.

That is a mitigation, not a guarantee. This is a reading aid, not a citable
source. Every digest links back to the original, and the claims that matter
should be checked against it.

## Layout

```
backend/
  app/
    models.py        the digest schema — start here
    ingest/          arxiv.py, pdf.py, sectionize.py
    distill/         prompt.py (the quality lives here), engine.py
    pipeline.py      source → parsed paper → digest
    jobs.py          in-process job registry behind the SSE stream
    main.py          the HTTP API
  tests/             75 tests, no network or API key required
frontend/
  src/
    components/      ThemeMap.tsx is the centrepiece
    types.ts         mirrors models.py
data/demo/           the bundled sample digest and the script that builds it
```

## Limitations

- **Scanned PDFs need OCR first.** Text extraction, not image understanding.
- **Papers are truncated at 80 pages.** Long appendices are dropped, and the
  digest says so when it happens.
- **Figures are not read.** A paper whose argument lives entirely in its figures
  will produce a thinner digest than one whose prose carries it.
- **Jobs are in-process.** Restarting the server loses running analyses. The
  digest cache on disk survives; `jobs.py` is the one file to replace if this
  ever needs to run as more than one process.

## Licence

MIT.
