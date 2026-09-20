import { useEffect, useMemo, useRef, useState } from "react";
import type { ConceptEdge, ConceptNode, NodeKind, ThemeMap as ThemeMapData } from "../types";

/* --------------------------------------------------------------------------
 * Layout
 *
 * A force simulation gives a different picture every run and buries the
 * argument in physics. Instead each kind of node owns a sector of the circle,
 * so the map always reads the same way: what was broken on the left, the
 * machinery across the top, supporting ideas on the right, consequences and
 * evidence along the bottom. Importance pulls a node towards the centre.
 * ------------------------------------------------------------------------ */

const W = 940;
const H = 600;
const CX = W / 2;
const CY = H / 2;
const SPREAD_X = 1.3;
const SPREAD_Y = 0.94;

/**
 * Angles in degrees, screen convention: 0 is east, 90 is south. Gaps between
 * sectors are deliberate: they keep neighbouring roles from running together,
 * so the eye can read "these are the problems, those are the methods".
 */
const SECTORS: Record<Exclude<NodeKind, "core">, [number, number]> = {
  problem: [150, 210],
  method: [240, 300],
  concept: [320, 355],
  implication: [10, 45],
  evidence: [75, 135],
};

export const KIND_COLOR: Record<NodeKind, string> = {
  core: "var(--core)",
  problem: "var(--problem)",
  method: "var(--method)",
  concept: "var(--concept)",
  evidence: "var(--evidence)",
  implication: "var(--implication)",
};

const KIND_LABEL: Record<NodeKind, string> = {
  core: "core idea",
  problem: "problem",
  method: "method",
  concept: "concept",
  evidence: "evidence",
  implication: "implication",
};

const CHAR_W = 6.6;
const LINE_H = 14;

/** Greedy wrap, so a two-word label never gets split across three lines. */
function wrap(text: string, maxChars: number): string[] {
  const words = text.split(/\s+/);
  const lines: string[] = [];
  let line = "";
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word;
    if (candidate.length > maxChars && line) {
      lines.push(line);
      line = word;
    } else {
      line = candidate;
    }
  }
  if (line) lines.push(line);
  return lines;
}

interface Placed {
  node: ConceptNode;
  x: number;
  y: number;
  hw: number;
  hh: number;
  lines: string[];
}

function place(nodes: ConceptNode[]): Placed[] {
  const core = nodes.find((n) => n.kind === "core") ?? nodes[0];
  const placed: Placed[] = [];

  const box = (node: ConceptNode, isCore: boolean): Pick<Placed, "hw" | "hh" | "lines"> => {
    const lines = wrap(node.label, isCore ? 16 : 15);
    const widest = Math.max(...lines.map((l) => l.length));
    const pad = isCore ? 26 : 16;
    return {
      lines,
      hw: Math.max(isCore ? 74 : 50, (widest * CHAR_W * (isCore ? 1.2 : 1)) / 2 + pad),
      hh: (lines.length * LINE_H) / 2 + (isCore ? 18 : 13),
    };
  };

  placed.push({ node: core, x: CX, y: CY, ...box(core, true) });

  // Group by kind so each sector can be divided evenly among its members.
  const byKind = new Map<string, ConceptNode[]>();
  for (const node of nodes) {
    if (node.id === core.id) continue;
    const kind = node.kind === "core" ? "concept" : node.kind;
    byKind.set(kind, [...(byKind.get(kind) ?? []), node]);
  }

  for (const [kind, members] of byKind) {
    const [from, to] = SECTORS[kind as Exclude<NodeKind, "core">] ?? SECTORS.concept;
    // Heaviest first, so the most important idea sits at the sector's middle.
    const ordered = [...members].sort((a, b) => b.weight - a.weight);

    ordered.forEach((node, index) => {
      // Inset the ends of the sector so a two-node sector does not straddle
      // its full width and brush against its neighbours.
      const span = to - from;
      const fraction =
        ordered.length === 1 ? 0.5 : 0.12 + (index / (ordered.length - 1)) * 0.76;
      const angle = ((from + span * fraction) * Math.PI) / 180;
      // Weight pulls a node inwards; the stagger keeps neighbours off one ring.
      const stagger = ordered.length > 2 ? (index % 2 === 0 ? 0 : 30) : 0;
      const radius = 248 - node.weight * 52 + stagger;
      placed.push({
        node,
        x: CX + Math.cos(angle) * radius * SPREAD_X,
        y: CY + Math.sin(angle) * radius * SPREAD_Y,
        ...box(node, false),
      });
    });
  }

  separate(placed);
  return placed;
}

/**
 * Nudge overlapping boxes apart.
 *
 * Sector placement gets the arrangement right but cannot know how wide a
 * label will render, so boxes from adjacent sectors sometimes collide. A few
 * passes of axis-aligned separation fix that while preserving the layout's
 * meaning, and being iterative-but-deterministic it still gives the same
 * picture every render.
 */
function separate(placed: Placed[], iterations = 90): void {
  const gap = 16;
  for (let pass = 0; pass < iterations; pass++) {
    let moved = false;

    for (let i = 1; i < placed.length; i++) {
      for (let j = 0; j < placed.length; j++) {
        if (i === j) continue;
        const a = placed[i];
        const b = placed[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const overlapX = a.hw + b.hw + gap - Math.abs(dx);
        const overlapY = a.hh + b.hh + gap - Math.abs(dy);
        if (overlapX <= 0 || overlapY <= 0) continue;

        moved = true;
        // Resolve along whichever axis needs the smaller correction, and keep
        // the core pinned so the map stays centred on the paper's claim.
        const pinned = j === 0;
        if (overlapX < overlapY) {
          const push = (overlapX / (pinned ? 1 : 2)) * (dx < 0 ? -1 : 1);
          a.x += push;
          if (!pinned) b.x -= push;
        } else {
          const push = (overlapY / (pinned ? 1 : 2)) * (dy < 0 ? -1 : 1);
          a.y += push;
          if (!pinned) b.y -= push;
        }
      }
    }

    if (!moved) break;
  }

  // Keep everything inside the viewBox after the pushing about.
  for (const item of placed) {
    item.x = Math.min(W - item.hw - 8, Math.max(item.hw + 8, item.x));
    item.y = Math.min(H - item.hh - 8, Math.max(item.hh + 8, item.y));
  }
}

/** Stop an edge at the node's border rather than running under its label. */
function edgeStop(from: Placed, to: Placed): { x: number; y: number } {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  if (dx === 0 && dy === 0) return { x: to.x, y: to.y };
  const scale = Math.min(
    dx === 0 ? Infinity : (to.hw + 6) / Math.abs(dx),
    dy === 0 ? Infinity : (to.hh + 6) / Math.abs(dy),
  );
  return { x: to.x - dx * scale, y: to.y - dy * scale };
}

interface Drawn {
  edge: ConceptEdge;
  path: string;
  lx: number;
  ly: number;
  lw: number;
}

/** Point on a quadratic bezier at parameter t. */
function bezierAt(
  t: number,
  p0: { x: number; y: number },
  c: { x: number; y: number },
  p2: { x: number; y: number },
): { x: number; y: number } {
  const u = 1 - t;
  return {
    x: u * u * p0.x + 2 * u * t * c.x + t * t * p2.x,
    y: u * u * p0.y + 2 * u * t * c.y + t * t * p2.y,
  };
}

function draw(
  edges: ConceptEdge[],
  byId: Map<string, Placed>,
  coreId: string,
  caption: string,
): Drawn[] {
  const drawn: Drawn[] = [];
  for (const edge of edges) {
    const a = byId.get(edge.source);
    const b = byId.get(edge.target);
    if (!a || !b) continue; // a dangling edge is dropped, not drawn to nowhere

    const start = edgeStop(b, a);
    const end = edgeStop(a, b);
    const mx = (start.x + end.x) / 2;
    const my = (start.y + end.y) / 2;

    // Edges that touch the core are radial already, so a straight line reads
    // best. Rim-to-rim edges bow outwards to keep clear of the centre.
    const touchesCore = edge.source === coreId || edge.target === coreId;
    let cx = mx;
    let cy = my;
    if (!touchesCore) {
      const ox = mx - CX;
      const oy = my - CY;
      const len = Math.hypot(ox, oy) || 1;
      const bow = Math.hypot(end.x - start.x, end.y - start.y) * 0.16;
      cx = mx + (ox / len) * bow;
      cy = my + (oy / len) * bow;
    }

    // Labels on core edges sit two thirds of the way out towards the rim
    // node. Parking them all at the midpoint piles every label on top of the
    // core, which is exactly where the map most needs to stay readable.
    const t = !touchesCore ? 0.5 : edge.source === coreId ? 0.68 : 0.32;
    const at = bezierAt(t, start, { x: cx, y: cy }, end);

    drawn.push({
      edge,
      path: `M ${start.x} ${start.y} Q ${cx} ${cy} ${end.x} ${end.y}`,
      lx: at.x,
      ly: at.y - 3,
      lw: edge.label.length * 5.5 + 10,
    });
  }

  // Treat the caption under the core node as something to route around.
  const core = byId.get(coreId);
  const obstacles = new Map(byId);
  if (core) {
    obstacles.set("__caption__", {
      ...core,
      y: core.y + core.hh + 22,
      hw: (caption.length * 6) / 2 + 8,
      hh: 9,
    });
  }

  deconflictLabels(drawn, obstacles);
  return drawn;
}

/**
 * Slide edge labels off each other and out from under the nodes.
 *
 * The anchor points are geometrically correct but take no account of how wide
 * the words render, so labels collide. Nudging them a few pixels keeps every
 * relationship readable while each stays next to the edge it names.
 */
function deconflictLabels(drawn: Drawn[], obstacles: Map<string, Placed>): void {
  const HALF_H = 8;
  const gap = 4;
  const boxes = [...obstacles.values()];

  for (let pass = 0; pass < 40; pass++) {
    let moved = false;

    for (let i = 0; i < drawn.length; i++) {
      const a = drawn[i];
      const ahw = a.lw / 2;

      // Labels must not sit on top of a node's own text.
      for (const node of boxes) {
        const dx = a.lx - node.x;
        const dy = a.ly - node.y;
        const ox = ahw + node.hw + gap - Math.abs(dx);
        const oy = HALF_H + node.hh + gap - Math.abs(dy);
        if (ox > 0 && oy > 0) {
          moved = true;
          if (ox < oy) a.lx += ox * (dx < 0 ? -1 : 1);
          else a.ly += oy * (dy < 0 ? -1 : 1);
        }
      }

      for (let j = i + 1; j < drawn.length; j++) {
        const b = drawn[j];
        const bhw = b.lw / 2;
        const dx = a.lx - b.lx;
        const dy = a.ly - b.ly;
        const ox = ahw + bhw + gap - Math.abs(dx);
        const oy = HALF_H * 2 + gap - Math.abs(dy);
        if (ox <= 0 || oy <= 0) continue;

        moved = true;
        // Vertical separation keeps a label near the edge it belongs to,
        // where sliding sideways would strand it over a different one.
        const push = (oy / 2) * (dy < 0 ? -1 : 1);
        a.ly += push;
        b.ly -= push;
      }
    }

    if (!moved) break;
  }
}

/* ------------------------------------------------------------------------ */

export default function ThemeMap({ map }: { map: ThemeMapData }) {
  const [active, setActive] = useState<string | null>(null);
  const canvas = useRef<HTMLDivElement>(null);

  // On a narrow screen the map pans rather than shrinking, and the interesting
  // part is the middle. Open there instead of against the left margin.
  useEffect(() => {
    const element = canvas.current;
    if (!element) return;
    const overflow = element.scrollWidth - element.clientWidth;
    if (overflow > 0) element.scrollLeft = overflow / 2;
  }, [map]);

  const { placed, byId, coreId, drawnEdges } = useMemo(() => {
    const placed = place(map.nodes);
    const byId = new Map(placed.map((p) => [p.node.id, p]));
    const coreId = (map.nodes.find((n) => n.kind === "core") ?? map.nodes[0])?.id ?? "";
    return {
      placed,
      byId,
      coreId,
      drawnEdges: draw(map.edges, byId, coreId, map.core),
    };
  }, [map]);

  const neighbours = useMemo(() => {
    if (!active) return new Set<string>();
    const set = new Set<string>([active]);
    for (const { source, target } of map.edges) {
      if (source === active) set.add(target);
      if (target === active) set.add(source);
    }
    return set;
  }, [active, map.edges]);

  const selected = active ? byId.get(active)?.node : undefined;
  const relations = useMemo(() => {
    if (!active) return [];
    return map.edges
      .filter((e) => e.source === active || e.target === active)
      .map((e) => {
        const otherId = e.source === active ? e.target : e.source;
        const other = byId.get(otherId)?.node;
        return {
          outgoing: e.source === active,
          label: e.label,
          other: other?.label ?? otherId,
          kind: other?.kind ?? "concept",
        };
      });
  }, [active, map.edges, byId]);

  const kindsPresent = Array.from(new Set(map.nodes.map((n) => n.kind)));

  return (
    <div className="map-wrap">
      <div className="map-canvas" ref={canvas}>
        <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Concept map. Central idea: ${map.core}. ${map.nodes.length} connected ideas.`}
        onClick={(event) => {
          // A click on the background clears the selection.
          if (event.target === event.currentTarget) setActive(null);
        }}
      >
        <defs>
          <radialGradient id="pp-glow">
            <stop offset="0%" stopColor="var(--core)" stopOpacity="0.16" />
            <stop offset="100%" stopColor="var(--core)" stopOpacity="0" />
          </radialGradient>
        </defs>

        <ellipse cx={CX} cy={CY} rx={230} ry={150} fill="url(#pp-glow)" />

        <g>
          {drawnEdges.map(({ edge, path, lx, ly, lw }, index) => {
            const lit =
              active !== null && (edge.source === active || edge.target === active);
            const dim = active !== null && !lit;
            return (
              <g key={`${edge.source}-${edge.target}-${index}`}>
                <path
                  className={`map-edge${lit ? " is-lit" : ""}${dim ? " is-dim" : ""}`}
                  d={path}
                />
                {/* A backing plate keeps the label legible where it crosses
                    another edge. */}
                <rect
                  className={`map-edge-plate${dim ? " is-dim" : ""}`}
                  x={lx - lw / 2}
                  y={ly - 9}
                  width={lw}
                  height={13}
                  rx={3}
                />
                <text
                  className={`map-edge-label${lit ? " is-lit" : ""}${dim ? " is-dim" : ""}`}
                  x={lx}
                  y={ly}
                >
                  {edge.label}
                </text>
              </g>
            );
          })}
        </g>

        {placed.map(({ node, x, y, hw, hh, lines }) => {
          const isCore = node.id === coreId;
          const dim = active !== null && !neighbours.has(node.id);
          const isActive = node.id === active;
          const color = KIND_COLOR[node.kind];
          return (
            <g
              key={node.id}
              className={`map-node${isCore ? " is-core" : ""}${dim ? " is-dim" : ""}`}
              tabIndex={0}
              role="button"
              aria-pressed={isActive}
              aria-label={`${node.label}. ${KIND_LABEL[node.kind]}. ${node.blurb}`}
              onClick={() => setActive(isActive ? null : node.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setActive(isActive ? null : node.id);
                }
              }}
              onMouseEnter={() => setActive(node.id)}
              onMouseLeave={() => setActive(null)}
            >
              <rect
                className="node-box"
                x={x - hw}
                y={y - hh}
                width={hw * 2}
                height={hh * 2}
                rx={isCore ? 18 : 10}
                fill={isCore ? color : `color-mix(in srgb, ${color} 15%, var(--surface-2))`}
                stroke={color}
                strokeWidth={isActive ? 2.4 : 1.4}
              />
              <text
                x={x}
                y={y - ((lines.length - 1) * LINE_H) / 2 + 4}
                textAnchor="middle"
                fontSize={isCore ? 15.5 : 12.5}
              >
                {lines.map((line, index) => (
                  <tspan key={line + index} x={x} dy={index === 0 ? 0 : LINE_H}>
                    {line}
                  </tspan>
                ))}
              </text>
            </g>
          );
        })}

          <text
            className="map-core-label"
            x={CX}
            y={CY + (byId.get(coreId)?.hh ?? 40) + 22}
          >
            {map.core}
          </text>
        </svg>
      </div>

      <div className="map-legend">
        {kindsPresent.map((kind) => (
          <span key={kind}>
            <i style={{ background: KIND_COLOR[kind] }} />
            {KIND_LABEL[kind]}
          </span>
        ))}
      </div>

      <div className="map-detail" aria-live="polite">
        {selected ? (
          <>
            <div className="kind" style={{ color: KIND_COLOR[selected.kind] }}>
              {KIND_LABEL[selected.kind]}
            </div>
            <h4>{selected.label}</h4>
            <p>{selected.blurb}</p>
            {relations.length > 0 && (
              <div className="rels">
                {relations.map((rel, index) => (
                  <span className="rel" key={index}>
                    {rel.outgoing ? (
                      <>
                        <b>{rel.label}</b> → {rel.other}
                      </>
                    ) : (
                      <>
                        {rel.other} <b>{rel.label}</b> → this
                      </>
                    )}
                  </span>
                ))}
              </div>
            )}
          </>
        ) : (
          <p className="map-hint">
            Hover or select any idea to see what it means and how it connects. The centre
            is the paper's core claim; everything else is arranged around it by role.
          </p>
        )}
      </div>
    </div>
  );
}
