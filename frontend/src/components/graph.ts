/** Layout, palette and geometry for the whole-paper graph view. */

import type { GraphEdge, GraphNode, NodeLabel } from "../types";

export const VIEW_W = 1000;
export const VIEW_H = 640;

/**
 * Ten node labels, four hues.
 *
 * A node-link graph is an all-pairs form: any two nodes can end up side by
 * side, so every pair of colours has to be separable, not just neighbours in a
 * legend. Enumerating the reference palette against that gate showed only four
 * of its hues clear it in both light and dark. Ten distinct colours would have
 * been a palette that merely looked varied.
 *
 * So colour carries the family and a second channel carries the member:
 * related labels share a hue, and the one that matters more is filled solidly
 * while its companion is faint and dashed. The Paper and Section labels take
 * neutrals, which need no hue separation at all. Every node also renders its
 * caption inside it, which is the secondary encoding the two warning-band
 * checks (dark green/yellow CVD, light yellow/magenta contrast) require.
 */
export const FAMILY: Record<NodeLabel, { hue: string; solid: boolean }> = {
  Concept: { hue: "var(--viz-1)", solid: true },
  Term: { hue: "var(--viz-1)", solid: false },
  Step: { hue: "var(--viz-2)", solid: true },
  Artifact: { hue: "var(--viz-2)", solid: false },
  Metric: { hue: "var(--viz-4)", solid: true },
  Contribution: { hue: "var(--viz-4)", solid: false },
  Limitation: { hue: "var(--viz-3)", solid: true },
  Prereq: { hue: "var(--viz-3)", solid: false },
  Paper: { hue: "var(--viz-ink)", solid: true },
  Section: { hue: "var(--viz-muted)", solid: false },
};

export const LABEL_ORDER: NodeLabel[] = [
  "Paper", "Concept", "Step", "Artifact", "Metric",
  "Contribution", "Limitation", "Term", "Prereq", "Section",
];

/**
 * Where each label sits, as an angle in degrees (0 east, 90 south).
 *
 * Read clockwise from the top it tells the paper's story: what it does, what
 * flows through it, what it achieved, what is new, what it cannot do, where to
 * read, its vocabulary, its ideas, what you need to know first.
 */
const ANCHOR: Record<NodeLabel, { angle: number; reach: number }> = {
  Paper: { angle: 0, reach: 0 },
  Step: { angle: 288, reach: 0.78 },
  Artifact: { angle: 330, reach: 1.0 },
  Metric: { angle: 18, reach: 0.82 },
  Contribution: { angle: 62, reach: 0.9 },
  Limitation: { angle: 105, reach: 0.95 },
  Section: { angle: 148, reach: 1.05 },
  Term: { angle: 190, reach: 1.05 },
  Concept: { angle: 228, reach: 0.72 },
  Prereq: { angle: 262, reach: 1.0 },
};

const REACH_X = 330;
const REACH_Y = 215;

export interface SimNode extends GraphNode {
  r: number;
  lines: string[];
  fontSize: number;
  anchorX: number;
  anchorY: number;
  x: number;
  y: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}

export interface SimLink {
  source: string | SimNode;
  target: string | SimNode;
  type: string;
  label: string;
  derived: boolean;
  twin: number;
}

function radiusFor(node: GraphNode): number {
  if (node.kind === "Paper") return 52;
  const base = node.kind === "Concept" || node.kind === "Step" ? 26 : 21;
  return base + node.weight * 17;
}

/** Split on spaces but also after hyphens, so "Self-attention" can wrap. */
function breakUp(label: string): string[] {
  return label
    .split(/\s+/)
    .flatMap((word) => word.split(/(?<=-)/))
    .filter(Boolean);
}

function wrapAt(words: string[], perLine: number): string[] {
  const lines: string[] = [];
  let line = "";
  for (const word of words) {
    const candidate = line && !line.endsWith("-") ? `${line} ${word}` : line + word;
    if (candidate.length > perLine && line) {
      lines.push(line);
      line = word;
    } else {
      line = candidate;
    }
  }
  if (line) lines.push(line);
  return lines;
}

/**
 * Fit a caption inside a circle, shrinking rather than truncating wherever it
 * can. A node reading "Self-atte…" tells the reader nothing.
 */
export function captionLines(label: string, radius: number): [string[], number] {
  const words = breakUp(label);
  const maxLines = radius >= 40 ? 3 : 2;
  const usable = radius * 1.64;

  let lines: string[] = [];
  let fontSize = 12.5;

  for (let size = 12.5; size >= 7.5; size -= 0.5) {
    const perLine = Math.max(4, Math.floor(usable / (size * 0.54)));
    const candidate = wrapAt(words, perLine);
    if (candidate.length <= maxLines && candidate.every((l) => l.length <= perLine)) {
      return [candidate, size];
    }
    lines = candidate;
    fontSize = size;
  }

  const perLine = Math.max(4, Math.floor(usable / (fontSize * 0.54)));
  const kept = lines.slice(0, maxLines);
  const last = kept.length - 1;
  if (kept[last] && kept[last].length > perLine - 1) {
    kept[last] = `${kept[last].slice(0, Math.max(1, perLine - 1))}…`;
  } else if (lines.length > maxLines) {
    kept[last] = `${kept[last]}…`;
  }
  return [kept, fontSize];
}

export function buildNodes(nodes: GraphNode[]): SimNode[] {
  const seen = new Map<string, number>();
  const total = new Map<string, number>();
  for (const node of nodes) total.set(node.kind, (total.get(node.kind) ?? 0) + 1);

  return nodes.map((node) => {
    const radius = radiusFor(node);
    const [lines, fontSize] = captionLines(node.label, radius);

    if (node.kind === "Paper") {
      return {
        ...node, r: radius, lines, fontSize,
        anchorX: VIEW_W / 2, anchorY: VIEW_H / 2,
        x: VIEW_W / 2, y: VIEW_H / 2,
        fx: VIEW_W / 2, fy: VIEW_H / 2,
      };
    }

    const index = seen.get(node.kind) ?? 0;
    seen.set(node.kind, index + 1);
    const count = total.get(node.kind) ?? 1;

    // Fan a label's members across an arc so a crowded one does not start
    // stacked on a single point.
    const arc = Math.min(64, 16 + count * 5);
    const offset = count === 1 ? 0 : (index / (count - 1) - 0.5) * arc;
    const { angle, reach } = ANCHOR[node.kind];
    const radians = ((angle + offset) * Math.PI) / 180;

    const anchorX = VIEW_W / 2 + Math.cos(radians) * REACH_X * reach;
    const anchorY = VIEW_H / 2 + Math.sin(radians) * REACH_Y * reach;

    return { ...node, r: radius, lines, fontSize, anchorX, anchorY, x: anchorX, y: anchorY };
  });
}

export function buildLinks(edges: GraphEdge[], known: Set<string>): SimLink[] {
  const pairSeen = new Map<string, number>();
  const links: SimLink[] = [];

  for (const edge of edges) {
    if (!known.has(edge.source) || !known.has(edge.target)) continue;
    const key = [edge.source, edge.target].sort().join("\u0000");
    const twin = pairSeen.get(key) ?? 0;
    pairSeen.set(key, twin + 1);
    links.push({
      source: edge.source, target: edge.target,
      type: edge.type, label: edge.label, derived: edge.derived, twin,
    });
  }
  return links;
}

export interface Geometry {
  path: string;
  labelX: number;
  labelY: number;
}

/** An arc clipped to both circles, leaving room for the arrowhead. */
export function linkGeometry(source: SimNode, target: SimNode, twin: number): Geometry | null {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.hypot(dx, dy);
  if (distance < 1) return null;

  const ux = dx / distance;
  const uy = dy / distance;
  const bow = twin === 0 ? 0 : (twin % 2 === 1 ? 1 : -1) * Math.ceil(twin / 2) * 30;

  const startX = source.x + ux * source.r;
  const startY = source.y + uy * source.r;
  const endX = target.x - ux * (target.r + 10);
  const endY = target.y - uy * (target.r + 10);

  const midX = (startX + endX) / 2 - uy * bow;
  const midY = (startY + endY) / 2 + ux * bow;

  return {
    path: `M ${startX} ${startY} Q ${midX} ${midY} ${endX} ${endY}`,
    labelX: 0.25 * startX + 0.5 * midX + 0.25 * endX,
    labelY: 0.25 * startY + 0.5 * midY + 0.25 * endY,
  };
}
