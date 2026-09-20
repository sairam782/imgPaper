/** Mirrors backend/app/models.py. Keep the two in step. */

export type NodeKind =
  | "core"
  | "problem"
  | "method"
  | "concept"
  | "evidence"
  | "implication";

export type ContribKind =
  | "method"
  | "theory"
  | "dataset"
  | "empirical"
  | "system"
  | "analysis";

export interface ConceptNode {
  id: string;
  label: string;
  kind: NodeKind;
  weight: number;
  blurb: string;
}

export interface ConceptEdge {
  source: string;
  target: string;
  label: string;
}

export interface ThemeMap {
  core: string;
  nodes: ConceptNode[];
  edges: ConceptEdge[];
}

export interface MethodStep {
  id: string;
  name: string;
  plain: string;
  why: string;
  inputs: string[];
  outputs: string[];
}

export interface Metric {
  name: string;
  dataset: string | null;
  value: number;
  baseline: number | null;
  baseline_name: string | null;
  unit: string | null;
  higher_is_better: boolean;
}

export interface Results {
  headline: string;
  metrics: Metric[];
  caveat: string | null;
}

export interface LayeredSummary {
  eli5: string;
  overview: string;
  technical: string;
}

export interface Contribution {
  title: string;
  detail: string;
  kind: ContribKind;
}

export interface GlossaryItem {
  term: string;
  plain: string;
}

export interface Prereq {
  concept: string;
  why: string;
  level: "essential" | "helpful";
}

export interface SectionDigest {
  heading: string;
  gist: string;
  key_points: string[];
}

export interface ReadingHop {
  order: number;
  target: string;
  why: string;
  minutes: number;
}

export interface Check {
  question: string;
  answer: string;
}

export interface PaperMeta {
  title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  arxiv_id: string | null;
  source_url: string | null;
  abstract: string | null;
}

export interface Digest {
  meta: PaperMeta;
  digest_id: string;
  generated_at: string;
  model: string;
  truncated: boolean;
  word_count: number;
  theme: string;
  tldr: string;
  problem: string;
  key_idea: string;
  summary: LayeredSummary;
  contributions: Contribution[];
  theme_map: ThemeMap;
  method: MethodStep[];
  results: Results;
  limitations: string[];
  glossary: GlossaryItem[];
  prereqs: Prereq[];
  sections: SectionDigest[];
  reading_path: ReadingHop[];
  checks: Check[];
}

export interface Health {
  ok: boolean;
  version: string;
  live: boolean;
  model: string | null;
  demo_available: boolean;
  cached_digests: number;
  stages: { id: string; label: string }[];
}

export interface JobSnapshot {
  job_id: string;
  status: "running" | "done" | "error";
  stage: string;
  detail: string;
  step: number;
  total_steps: number;
  error?: string;
  digest?: Digest;
}
