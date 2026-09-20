import { useState } from "react";
import type {
  Check,
  Contribution,
  GlossaryItem,
  Prereq,
  ReadingHop,
  SectionDigest,
} from "../types";

export function Contributions({ items }: { items: Contribution[] }) {
  return (
    <div className="stack">
      {items.map((item, index) => (
        <article className="contribution" key={index}>
          <span className="tag">{item.kind}</span>
          <h4>{item.title}</h4>
          <p>{item.detail}</p>
        </article>
      ))}
    </div>
  );
}

export function Limitations({ items }: { items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div className="card">
      {items.map((item, index) => (
        <div className="limit" key={index}>
          <span>{item}</span>
        </div>
      ))}
    </div>
  );
}

export function Prereqs({ items }: { items: Prereq[] }) {
  if (items.length === 0) return null;
  return (
    <div className="card">
      {items.map((item, index) => (
        <div className="prereq" key={index}>
          <span className={`level${item.level === "essential" ? " is-essential" : ""}`}>
            {item.level}
          </span>
          <div>
            <h4>{item.concept}</h4>
            <p>{item.why}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

export function Glossary({ items }: { items: GlossaryItem[] }) {
  if (items.length === 0) return null;
  return (
    <dl className="term-grid">
      {items.map((item) => (
        <div className="term" key={item.term}>
          <dt>{item.term}</dt>
          <dd>{item.plain}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ReadingPath({ hops }: { hops: ReadingHop[] }) {
  if (hops.length === 0) return null;
  const total = hops.reduce((sum, hop) => sum + hop.minutes, 0);
  return (
    <>
      <div className="path">
        {[...hops]
          .sort((a, b) => a.order - b.order)
          .map((hop) => (
            <div className="hop" key={hop.order}>
              <h4>{hop.target}</h4>
              <p>{hop.why}</p>
              <span className="mins">{hop.minutes} min</span>
            </div>
          ))}
      </div>
      <div className="depth-note">
        {total} minutes end to end, instead of reading the whole thing.
      </div>
    </>
  );
}

export function Sections({ items }: { items: SectionDigest[] }) {
  const [open, setOpen] = useState<number | null>(0);
  if (items.length === 0) return null;

  return (
    <div className="card" style={{ padding: "4px 16px" }}>
      {items.map((section, index) => {
        const isOpen = open === index;
        return (
          <div className="accordion" key={`${section.heading}-${index}`}>
            <button
              className="accordion-head"
              aria-expanded={isOpen}
              onClick={() => setOpen(isOpen ? null : index)}
            >
              <h4>{section.heading}</h4>
              <span className="gist">{section.gist}</span>
              <span className="caret" aria-hidden="true">
                {isOpen ? "▲" : "▼"}
              </span>
            </button>
            {isOpen && section.key_points.length > 0 && (
              <div className="accordion-body">
                <ul>
                  {section.key_points.map((point, pointIndex) => (
                    <li key={pointIndex}>{point}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/** Questions that reveal whether the reader actually followed the paper. */
export function Checks({ items }: { items: Check[] }) {
  const [revealed, setRevealed] = useState<Set<number>>(new Set());
  if (items.length === 0) return null;

  const toggle = (index: number) =>
    setRevealed((previous) => {
      const next = new Set(previous);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });

  return (
    <div className="checks">
      {items.map((check, index) => {
        const isOpen = revealed.has(index);
        return (
          <button
            className="check"
            key={index}
            aria-expanded={isOpen}
            onClick={() => toggle(index)}
          >
            <q>{check.question}</q>
            {isOpen ? (
              <p className="answer">{check.answer}</p>
            ) : (
              <span className="reveal">Show answer</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
