import { useCallback, useEffect, useRef, useState } from "react";
import { followJob, getDemo, getHealth, startSourceJob, startUploadJob } from "./api";
import DigestView from "./components/DigestView";
import Ingest from "./components/Ingest";
import Progress from "./components/Progress";
import type { Digest, Health, JobSnapshot } from "./types";

type View =
  | { kind: "idle" }
  | { kind: "running"; detail: string; step: number; totalSteps: number }
  | { kind: "ready"; digest: Digest };

const STEPS = [
  {
    title: "Give it a paper",
    body: "An arXiv link, a PDF, or pasted text. It is fetched, parsed, and split back into sections.",
  },
  {
    title: "It reads the whole thing",
    body: "Long papers are worked through section by section first, so nothing past page eight gets skipped.",
  },
  {
    title: "You get a map, not a wall",
    body: "A theme map of the argument, the method as a pipeline, the evidence as charts, and a summary at three depths.",
  },
];

function useTheme() {
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    const saved = localStorage.getItem("pp-theme");
    if (saved === "light" || saved === "dark") return saved;
    return window.matchMedia?.("(prefers-color-scheme: light)").matches ? "light" : "dark";
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("pp-theme", theme);
  }, [theme]);

  return [theme, () => setTheme((t) => (t === "dark" ? "light" : "dark"))] as const;
}

export default function App() {
  const [view, setView] = useState<View>({ kind: "idle" });
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [theme, toggleTheme] = useTheme();
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  // A run that is still going when the component unmounts must not keep its
  // EventSource open.
  useEffect(() => () => abort.current?.abort(), []);

  const run = useCallback(async (start: () => Promise<string>) => {
    abort.current?.abort();
    const controller = new AbortController();
    abort.current = controller;

    setError(null);
    setView({ kind: "running", detail: "Fetching the paper", step: 0, totalSteps: 4 });

    try {
      const jobId = await start();
      const digest = await followJob(
        jobId,
        (snapshot: JobSnapshot) =>
          setView({
            kind: "running",
            detail: snapshot.detail,
            step: snapshot.step,
            totalSteps: snapshot.total_steps,
          }),
        controller.signal,
      );
      setView({ kind: "ready", digest });
      window.scrollTo({ top: 0 });
    } catch (caught) {
      if (caught instanceof DOMException && caught.name === "AbortError") {
        setView({ kind: "idle" });
        return;
      }
      setError(caught instanceof Error ? caught.message : "Something went wrong.");
      setView({ kind: "idle" });
    }
  }, []);

  const showDemo = useCallback(async () => {
    setError(null);
    try {
      const digest = await getDemo();
      setView({ kind: "ready", digest });
      window.scrollTo({ top: 0 });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The example is unavailable.");
    }
  }, []);

  const reset = () => {
    abort.current?.abort();
    setView({ kind: "idle" });
    setError(null);
  };

  return (
    <>
      <div className="topbar">
        <div className="wordmark">
          <svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true">
            <path d="M11 2 L20 19 L2 19 Z" fill="none" stroke="var(--text)" strokeWidth="1.5" strokeLinejoin="round" />
            <path d="M2 13 L20 13" stroke="var(--core)" strokeWidth="1.5" />
            <path d="M20 13 L21.5 10.5" stroke="var(--problem)" strokeWidth="1.5" />
            <path d="M20 13 L21.5 13" stroke="var(--evidence)" strokeWidth="1.5" />
            <path d="M20 13 L21.5 15.5" stroke="var(--method)" strokeWidth="1.5" />
          </svg>
          PaperPrism
        </div>

        <span className="topbar-spacer" />

        {health && (
          <span className={`pill ${health.live ? "is-live" : "is-demo"}`}>
            {health.live ? health.model : "demo mode"}
          </span>
        )}

        <button
          className="icon-button"
          onClick={toggleTheme}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>
      </div>

      <main className="shell">
        {view.kind === "idle" && (
          <div className="landing rise">
            <h1>
              Research papers you can <em>see</em>
            </h1>
            <p className="lede">
              Paste a paper. Get back a map of its argument, its method drawn as a
              pipeline, its evidence charted against the baselines, and a summary that
              scales from “explain it simply” to the full technical account.
            </p>

            <Ingest
              onSubmit={(source) => run(() => startSourceJob(source))}
              onUpload={(file) => run(() => startUploadJob(file))}
              onDemo={showDemo}
              live={health?.live ?? false}
              busy={false}
            />

            {error && (
              <div className="notice" role="alert">
                {error}
              </div>
            )}

            <div className="how">
              {STEPS.map((step, index) => (
                <article key={step.title}>
                  <span className="num">0{index + 1}</span>
                  <h3>{step.title}</h3>
                  <p>{step.body}</p>
                </article>
              ))}
            </div>
          </div>
        )}

        {view.kind === "running" && (
          <Progress
            detail={view.detail}
            step={view.step}
            totalSteps={view.totalSteps}
            onCancel={reset}
          />
        )}

        {view.kind === "ready" && <DigestView digest={view.digest} onReset={reset} />}
      </main>
    </>
  );
}
