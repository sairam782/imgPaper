import { useRef, useState } from "react";

const EXAMPLES = [
  { id: "1706.03762", label: "Attention Is All You Need" },
  { id: "1512.03385", label: "ResNet" },
  { id: "1810.04805", label: "BERT" },
  { id: "2005.14165", label: "GPT-3" },
];

interface Props {
  onSubmit: (source: string) => void;
  onUpload: (file: File) => void;
  onDemo: () => void;
  live: boolean;
  busy: boolean;
}

export default function Ingest({ onSubmit, onUpload, onDemo, live, busy }: Props) {
  const [value, setValue] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  const submit = () => {
    const trimmed = value.trim();
    if (trimmed && !busy) onSubmit(trimmed);
  };

  return (
    <div className="ingest">
      <div className="ingest-field">
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            // Enter submits; Shift+Enter is for pasting multi-line text.
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault();
              submit();
            }
          }}
          placeholder="Paste an arXiv link, a PDF URL, or the paper's text…"
          aria-label="Paper source"
          rows={1}
          style={{ height: value.includes("\n") ? 140 : undefined }}
        />
        <button className="primary" onClick={submit} disabled={busy || !value.trim()}>
          Refract
        </button>
      </div>

      <div className="ingest-aux">
        <span>Try</span>
        {EXAMPLES.map((example) => (
          <button
            key={example.id}
            className="chip"
            disabled={busy}
            onClick={() => {
              setValue(example.id);
              onSubmit(example.id);
            }}
          >
            {example.label}
          </button>
        ))}
        <span>·</span>
        <button className="chip" disabled={busy} onClick={() => fileInput.current?.click()}>
          Upload a PDF
        </button>
        <button className="chip" onClick={onDemo}>
          See a finished example
        </button>
        <input
          ref={fileInput}
          type="file"
          accept="application/pdf,.pdf"
          hidden
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onUpload(file);
            event.target.value = "";
          }}
        />
      </div>

      {!live && (
        <div className="notice is-info">
          <strong>No API key configured.</strong> Set <code>ANTHROPIC_API_KEY</code> to
          analyse real papers. Until then, “See a finished example” opens a complete
          pre-built digest so you can explore everything the app does.
        </div>
      )}
    </div>
  );
}
