import type { Digest } from "../types";
import DepthDial from "./DepthDial";
import MethodFlow from "./MethodFlow";
import { Checks, Contributions, Glossary, Limitations, Prereqs, ReadingPath, Sections } from "./Panels";
import ResultsChart from "./ResultsChart";
import ThemeMap from "./ThemeMap";

function Block({
  id,
  title,
  blurb,
  children,
}: {
  id: string;
  title: string;
  blurb?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="block" id={id} aria-labelledby={`${id}-title`}>
      <header className="block-head">
        <h2 id={`${id}-title`}>{title}</h2>
        {blurb && <p>{blurb}</p>}
      </header>
      {children}
    </section>
  );
}

function byline(digest: Digest): string {
  const { authors, year, venue } = digest.meta;
  const names =
    authors.length === 0
      ? null
      : authors.length > 3
        ? `${authors.slice(0, 3).join(", ")} and ${authors.length - 3} others`
        : authors.join(", ");
  return [names, venue, year ? String(year) : null].filter(Boolean).join(" · ");
}

export default function DigestView({ digest, onReset }: { digest: Digest; onReset: () => void }) {
  const credit = byline(digest);

  return (
    <div className="digest rise">
      <header className="paper-head">
        <h1>{digest.meta.title}</h1>
        <div className="byline">
          {credit && <span>{credit}</span>}
          {digest.meta.source_url && (
            <a href={digest.meta.source_url} target="_blank" rel="noreferrer">
              View the original ↗
            </a>
          )}
          <button className="chip" onClick={onReset}>
            Analyse another
          </button>
        </div>

        <div className="theme-banner">
          <div className="eyebrow">The main theme</div>
          <div className="theme">{digest.theme}</div>
          <p className="tldr">{digest.tldr}</p>
        </div>

        {digest.truncated && (
          <div className="notice is-info is-inline">
            This paper was longer than the extraction budget, so the later sections were
            not read. Treat the digest as covering the first part of the paper.
          </div>
        )}
      </header>

      <Block
        id="map"
        title="The paper as a map"
        blurb="Every idea in the paper and how it connects, arranged by the role it plays in the argument."
      >
        <ThemeMap map={digest.theme_map} />
      </Block>

      <Block
        id="summary"
        title="The summary, at your depth"
        blurb="The same paper explained three times over, for three different readers."
      >
        <DepthDial summary={digest.summary} />
      </Block>

      <Block id="crux" title="The problem and the move">
        <div className="grid-2">
          <div className="card">
            <div className="eyebrow">What was wrong before</div>
            <p>{digest.problem}</p>
          </div>
          <div className="card" style={{ borderLeft: "3px solid var(--core)" }}>
            <div className="eyebrow">The idea that fixes it</div>
            <p>{digest.key_idea}</p>
          </div>
        </div>
      </Block>

      {digest.method.length > 0 && (
        <Block
          id="method"
          title="How it actually works"
          blurb="The method as ordered stages. Select a stage to see what it does and why it is there."
        >
          <MethodFlow steps={digest.method} />
        </Block>
      )}

      <Block id="results" title="What the evidence shows" blurb={digest.results.headline}>
        <ResultsChart metrics={digest.results.metrics} />
        {digest.results.caveat && (
          <div className="notice is-info is-inline" style={{ marginTop: 16 }}>
            <strong>What it does not show. </strong>
            {digest.results.caveat}
          </div>
        )}
      </Block>

      <Block id="contributions" title="What is new here">
        <Contributions items={digest.contributions} />
      </Block>

      {digest.limitations.length > 0 && (
        <Block
          id="limits"
          title="Where it stops"
          blurb="The honest limits, including ones the paper itself moves past quickly."
        >
          <Limitations items={digest.limitations} />
        </Block>
      )}

      {digest.reading_path.length > 0 && (
        <Block
          id="path"
          title="If you only read part of it"
          blurb="A route through the paper for someone who will not read it front to back."
        >
          <ReadingPath hops={digest.reading_path} />
        </Block>
      )}

      {digest.prereqs.length > 0 && (
        <Block id="prereqs" title="What to know first">
          <Prereqs items={digest.prereqs} />
        </Block>
      )}

      {digest.sections.length > 0 && (
        <Block id="sections" title="Section by section">
          <Sections items={digest.sections} />
        </Block>
      )}

      {digest.glossary.length > 0 && (
        <Block
          id="glossary"
          title="The jargon, decoded"
          blurb="Each term as this paper uses it, not as a dictionary would define it."
        >
          <Glossary items={digest.glossary} />
        </Block>
      )}

      {digest.checks.length > 0 && (
        <Block
          id="checks"
          title="Did it land?"
          blurb="Answer these from memory. If one stalls, the section it comes from is worth a second pass."
        >
          <Checks items={digest.checks} />
        </Block>
      )}

      <footer className="digest-foot">
        <span>{digest.model === "demo" ? "bundled example" : digest.model}</span>
        {digest.word_count > 0 && <span>{digest.word_count.toLocaleString()} words read</span>}
        {digest.meta.arxiv_id && <span>arXiv:{digest.meta.arxiv_id}</span>}
        <span className="spacer" />
        <span>{digest.digest_id}</span>
      </footer>
    </div>
  );
}
