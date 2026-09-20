import type { Metric } from "../types";

function format(value: number, unit: string | null): string {
  const rounded = Number.isInteger(value) ? String(value) : value.toFixed(2).replace(/0$/, "");
  return unit ? `${rounded} ${unit}` : rounded;
}

/**
 * Bars are scaled against the larger of the two values in the row, so a 2%
 * improvement is not drawn as a doubling. Metrics with no baseline get no bar
 * at all -- a lone full-width bar reads as "the maximum", which is a claim the
 * paper did not make.
 */
function widths(metric: Metric): { result: number; baseline: number } {
  const baseline = metric.baseline ?? 0;
  const top = Math.max(Math.abs(metric.value), Math.abs(baseline)) || 1;
  return {
    result: (Math.abs(metric.value) / top) * 100,
    baseline: (Math.abs(baseline) / top) * 100,
  };
}

function delta(metric: Metric): { text: string; worse: boolean } | null {
  if (metric.baseline === null || metric.baseline === 0) return null;
  const change = ((metric.value - metric.baseline) / Math.abs(metric.baseline)) * 100;
  const improved = metric.higher_is_better ? change > 0 : change < 0;
  return {
    text: `${change > 0 ? "+" : ""}${change.toFixed(1)}%`,
    worse: !improved,
  };
}

export default function ResultsChart({ metrics }: { metrics: Metric[] }) {
  if (metrics.length === 0) {
    return (
      <p className="map-hint">
        This paper reports no comparable headline numbers, so there is nothing to chart.
      </p>
    );
  }

  return (
    <div className="card">
      {metrics.map((metric, index) => {
        const compared = metric.baseline !== null;
        const bar = widths(metric);
        const change = delta(metric);

        return (
          <div
            className={`metric${compared ? "" : " is-stat"}`}
            key={`${metric.name}-${metric.dataset}-${index}`}
          >
            <div className="metric-head">
              <span className="metric-name">
                {metric.name}
                {metric.dataset && <span className="metric-dataset"> · {metric.dataset}</span>}
              </span>
              <span className="metric-value">{format(metric.value, metric.unit)}</span>
            </div>

            {compared ? (
              <>
                <div className="bar-row">
                  <span>this paper</span>
                  <div className="bar-track">
                    <div className="bar-fill" style={{ width: `${bar.result}%` }} />
                  </div>
                  <span className={`delta${change?.worse ? " is-worse" : ""}`}>
                    {change?.text ?? ""}
                  </span>
                </div>

                <div className="bar-row">
                  <span title={metric.baseline_name ?? "baseline"}>baseline</span>
                  <div className="bar-track">
                    <div
                      className="bar-fill is-baseline"
                      style={{ width: `${bar.baseline}%` }}
                    />
                  </div>
                  <span>{format(metric.baseline as number, metric.unit)}</span>
                </div>

                <div className="io" style={{ marginTop: 6 }}>
                  {metric.baseline_name && (
                    <span>
                      <b>vs</b> {metric.baseline_name}
                    </span>
                  )}
                  <span>
                    <b>{metric.higher_is_better ? "higher" : "lower"} is better</b>
                  </span>
                </div>
              </>
            ) : (
              <div className="io">
                <span>reported on its own, with no baseline to compare against</span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
