import { useState } from "react";
import type { LayeredSummary } from "../types";

type Level = keyof LayeredSummary;

const LEVELS: { id: Level; label: string; note: string }[] = [
  { id: "eli5", label: "Explain simply", note: "No jargon. Written for someone outside the field." },
  { id: "overview", label: "Overview", note: "For a researcher in an adjacent field." },
  { id: "technical", label: "Technical", note: "For someone who might build on this work." },
];

/** The same paper at three depths. Each level is written to stand alone. */
export default function DepthDial({ summary }: { summary: LayeredSummary }) {
  const [level, setLevel] = useState<Level>("eli5");
  const active = LEVELS.find((l) => l.id === level)!;

  return (
    <>
      <div className="dial" role="tablist" aria-label="Summary depth">
        {LEVELS.map((item) => (
          <button
            key={item.id}
            role="tab"
            aria-selected={item.id === level}
            aria-controls="summary-body"
            className={item.id === level ? "is-on" : ""}
            onClick={() => setLevel(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <div
        className={`summary-body${level === "eli5" ? " is-eli5" : ""}`}
        id="summary-body"
        role="tabpanel"
      >
        {summary[level].split("\n\n").map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
      </div>

      <div className="depth-note">{active.note}</div>
    </>
  );
}
