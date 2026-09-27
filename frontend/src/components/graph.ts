/** Layout and geometry for the Neo4j-style graph view. */

import type { ConceptEdge, ConceptNode, NodeKind } from "../types";

export const VIEW_W = 1000;
export const VIEW_H = 640;

export const KIND_COLOR: Record<NodeKind, string> = {
  core: "var(--core)",
  problem: "var(--problem)",
  method: "var(--method)",
  concept: "var(--concept)",
  evidence: "var(--evidence)",
  implication: "var(--implication)",
};

export const KIND_LABEL: Record<NodeKind, string> = {
  core: "CoreIdea",
  problem: "Problem",
  method: "Method",
  concept: "Concept",
  evidence: "Evidence",
  implication: "Implication",
};

/**
 * Where each kind of node belongs on the canvas, as an angle in degrees
 * (0 is east, 90 is south).
 *
 * The simulation is pulled gently towards these anchors rather than left to
 * settle wherever physics takes it. A pure force layout arranges a graph by
 * edge count, which would throw away the one thing that makes this map worth
 * reading: that position means role. Problems sit left, the machinery runs
 * across the top, consequences and evidence fall to the right and bottom.
 */
const ANCHOR_ANGLE: Record<Exclude<NodeKind, "core">, number> = {
  problem: 180,
  method: 278,
  concept: 345,
  implication: 35,
  evidence: 100,
};

const ANCHOR_RADIUS_X = 330;
const ANCHOR_RADIUS_Y = 210;

export interface SimNode extends ConceptNode {
  r: number;
  lines: string[];
  fontSize: number;
  anchorX: number;
  anchorY: number;
  // Written by d3-force.
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
  label: string;
  /** Index among links sharing this pair, so parallel edges fan out. */
  twin: number;
}

/** Node size follows importance, the way Neo4j sizes by degree. */
function radiusFor(node: ConceptNode): number {
  if (node.kind === "core") return 58;
  return 34 + node.weight * 22;
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
 * Fit a caption inside a circle.
 *
 * Rather than truncating at a fixed size, this shrinks the text until the
 * whole label fits, and only truncates when even the smallest size will not
 * do. A node reading "Self-atte…" tells the reader nothing.
 */
export function captionLines(label: string, radius: number): [string[], number] {
  const words = breakUp(label);
  const maxLines = radius >= 46 ? 3 : 2;
  const usable = radius * 1.66;

  let lines: string[] = [];
  let fontSize = 13.5;

  for (let size = 13.5; size >= 8.5; size -= 0.5) {
    const perLine = Math.max(4, Math.floor(usable / (size * 0.54)));
    const candidate = wrapAt(words, perLine);
    if (candidate.length <= maxLines && candidate.every((l) => l.length <= perLine)) {
      return [candidate, size];
    }
    lines = candidate;
    fontSize = size;
  }

  // Nothing fits; keep what we can and mark the cut.
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

export function buildNodes(nodes: ConceptNode[]): SimNode[] {
  const coreId = (nodes.find((n) => n.kind === "core") ?? nodes[0])?.id;

  // Spread same-kind nodes around their anchor so they do not start stacked.
  const seen = new Map<string, number>();
  const total = new Map<string, number>();
  for (const node of nodes) {
    total.set(node.kind, (total.get(node.kind) ?? 0) + 1);
  }

  return nodes.map((node) => {
    const radius = radiusFor(node);
    const [lines, fontSize] = captionLines(node.label, radius);

    if (node.id === coreId) {
      return {
        ...node,
        r: radius,
        lines,
        fontSize,
        anchorX: VIEW_W / 2,
        anchorY: VIEW_H / 2,
        x: VIEW_W / 2,
        y: VIEW_H / 2,
        fx: VIEW_W / 2,
        fy: VIEW_H / 2,
      };
    }

    const index = seen.get(node.kind) ?? 0;
    seen.set(node.kind, index + 1);
    const count = total.get(node.kind) ?? 1;
    const spread = count === 1 ? 0 : (index / (count - 1) - 0.5) * 54;

    const angle = ((ANCHOR_ANGLE[node.kind as Exclude<NodeKind, "core">] ?? 0) + spread) * (Math.PI / 180);
    const anchorX = VIEW_W / 2 + Math.cos(angle) * ANCHOR_RADIUS_X;
    const anchorY = VIEW_H / 2 + Math.sin(angle) * ANCHOR_RADIUS_Y;

    return {
      ...node,
      r: radius,
      lines,
      fontSize,
      anchorX,
      anchorY,
      x: anchorX,
      y: anchorY,
    };
  });
}

export function buildLinks(edges: ConceptEdge[], known: Set<string>): SimLink[] {
  const pairSeen = new Map<string, number>();
  const links: SimLink[] = [];

  for (const edge of edges) {
    // A relationship to a node that does not exist is dropped rather than
    // drawn into empty space.
    if (!known.has(edge.source) || !known.has(edge.target)) continue;
    const key = [edge.source, edge.target].sort().join("\u0000");
    const twin = pairSeen.get(key) ?? 0;
    pairSeen.set(key, twin + 1);
    links.push({ source: edge.source, target: edge.target, label: edge.label, twin });
  }
  return links;
}

export interface Geometry {
  path: string;
  labelX: number;
  labelY: number;
}

/**
 * An arc between two circles, clipped to their edges so it starts and ends at
 * the rim rather than under the caption, leaving room for the arrowhead.
 */
export function linkGeometry(source: SimNode, target: SimNode, twin: number): Geometry | null {
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const distance = Math.hypot(dx, dy);
  if (distance < 1) return null;

  const ux = dx / distance;
  const uy = dy / distance;

  // Parallel relationships bow apart so both stay readable.
  const bow = twin === 0 ? 0 : (twin % 2 === 1 ? 1 : -1) * Math.ceil(twin / 2) * 34;

  const startX = source.x + ux * source.r;
  const startY = source.y + uy * source.r;
  const endX = target.x - ux * (target.r + 11);
  const endY = target.y - uy * (target.r + 11);

  const midX = (startX + endX) / 2 - uy * bow;
  const midY = (startY + endY) / 2 + ux * bow;

  return {
    path: `M ${startX} ${startY} Q ${midX} ${midY} ${endX} ${endY}`,
    // Midpoint of the quadratic, which is where the type label sits.
    labelX: 0.25 * startX + 0.5 * midX + 0.25 * endX,
    labelY: 0.25 * startY + 0.5 * midY + 0.25 * endY,
  };
}
