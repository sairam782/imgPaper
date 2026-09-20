import type { Digest, Health, JobSnapshot } from "./types";

/** Server errors carry a useful `detail`; surface it rather than a status code. */
async function failure(response: Response): Promise<Error> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return new Error(body.detail);
  } catch {
    /* fall through to the generic message */
  }
  return new Error(`Request failed (${response.status})`);
}

export async function getHealth(): Promise<Health> {
  const response = await fetch("/api/health");
  if (!response.ok) throw await failure(response);
  return response.json();
}

export async function getDemo(): Promise<Digest> {
  const response = await fetch("/api/demo");
  if (!response.ok) throw await failure(response);
  return response.json();
}

async function startJob(body: BodyInit, headers?: HeadersInit): Promise<string> {
  const response = await fetch(
    body instanceof FormData ? "/api/jobs/upload" : "/api/jobs",
    { method: "POST", body, headers },
  );
  if (!response.ok) throw await failure(response);
  const { job_id } = await response.json();
  return job_id;
}

export function startSourceJob(source: string): Promise<string> {
  return startJob(JSON.stringify({ source }), { "Content-Type": "application/json" });
}

export function startUploadJob(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  return startJob(form);
}

/**
 * Follow a job to completion over server-sent events.
 *
 * `onProgress` fires for every stage change. The promise settles once the job
 * finishes, and the stream is always closed, including when the caller aborts.
 */
export function followJob(
  jobId: string,
  onProgress: (snapshot: JobSnapshot) => void,
  signal?: AbortSignal,
): Promise<Digest> {
  return new Promise((resolve, reject) => {
    const source = new EventSource(`/api/jobs/${jobId}/events`);

    const close = () => {
      source.close();
      signal?.removeEventListener("abort", onAbort);
    };
    const onAbort = () => {
      close();
      reject(new DOMException("Cancelled", "AbortError"));
    };
    signal?.addEventListener("abort", onAbort);

    source.onmessage = (event) => {
      let snapshot: JobSnapshot;
      try {
        snapshot = JSON.parse(event.data);
      } catch {
        return;
      }
      onProgress(snapshot);

      if (snapshot.status === "done" && snapshot.digest) {
        close();
        resolve(snapshot.digest);
      } else if (snapshot.status === "error") {
        close();
        reject(new Error(snapshot.error ?? "The analysis failed."));
      }
    };

    source.onerror = () => {
      // EventSource retries by itself; a failure here means the stream is gone.
      if (source.readyState === EventSource.CLOSED) {
        close();
        reject(new Error("Lost the connection to the server."));
      }
    };
  });
}
