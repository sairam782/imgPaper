import { useState } from "react";
import type { MethodStep } from "../types";

/** The paper's method as an ordered pipeline you can step through. */
export default function MethodFlow({ steps }: { steps: MethodStep[] }) {
  const [current, setCurrent] = useState(0);
  if (steps.length === 0) return null;

  const step = steps[Math.min(current, steps.length - 1)];

  return (
    <>
      <div className="flow" role="tablist" aria-label="Method steps">
        {steps.map((item, index) => (
          <div key={item.id} style={{ display: "contents" }}>
            {index > 0 && (
              <span className="flow-arrow" aria-hidden="true">
                →
              </span>
            )}
            <button
              role="tab"
              id={`step-tab-${item.id}`}
              aria-selected={index === current}
              aria-controls="step-detail"
              className={`flow-step${index === current ? " is-on" : ""}`}
              onClick={() => setCurrent(index)}
            >
              <span className="step-n">
                {String(index + 1).padStart(2, "0")}
              </span>
              <h4>{item.name}</h4>
            </button>
          </div>
        ))}
      </div>

      <div
        className="flow-detail"
        id="step-detail"
        role="tabpanel"
        aria-labelledby={`step-tab-${step.id}`}
      >
        <h4>{step.name}</h4>
        <p>{step.plain}</p>
        <div className="why">
          <strong>Why this step exists: </strong>
          {step.why}
        </div>
        <div className="io">
          {step.inputs.length > 0 && (
            <span>
              <b>in</b> {step.inputs.join(" · ")}
            </span>
          )}
          {step.outputs.length > 0 && (
            <span>
              <b>out</b> {step.outputs.join(" · ")}
            </span>
          )}
        </div>
      </div>
    </>
  );
}
