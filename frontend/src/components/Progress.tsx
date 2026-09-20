interface Props {
  detail: string;
  step: number;
  totalSteps: number;
  onCancel: () => void;
}

export default function Progress({ detail, step, totalSteps, onCancel }: Props) {
  const bars = Array.from({ length: Math.max(totalSteps, 1) });

  return (
    <div className="progress" role="status" aria-live="polite">
      <div className="progress-detail">{detail}…</div>

      <div className="progress-track">
        {bars.map((_, index) => (
          <span
            key={index}
            className={index < step ? "is-done" : index === step ? "is-active" : ""}
          />
        ))}
      </div>

      <small>
        Reading the whole paper takes a little while. Long papers are worked through
        section by section first.
      </small>

      <div>
        <button className="ghost" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
