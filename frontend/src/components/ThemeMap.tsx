import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
  forceX,
  forceY,
  type Simulation,
} from "d3-force";

import { exportCypher } from "../api";
import type { NodeKind, ThemeMap as ThemeMapData } from "../types";
import {
  buildLinks,
  buildNodes,
  KIND_COLOR,
  KIND_LABEL,
  linkGeometry,
  VIEW_H,
  VIEW_W,
  type SimLink,
  type SimNode,
} from "./graph";

const MIN_ZOOM = 0.4;
const MAX_ZOOM = 2.6;

interface View {
  k: number;
  x: number;
  y: number;
}

interface Relationship {
  dir: "in" | "out";
  type: string;
  other: SimNode;
}

const IDENTITY: View = { k: 1, x: 0, y: 0 };

export default function ThemeMap({ map, title }: { map: ThemeMapData; title?: string }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const simRef = useRef<Simulation<SimNode, SimLink> | null>(null);

  const [selected, setSelected] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [muted, setMuted] = useState<Set<NodeKind>>(new Set());
  const [view, setView] = useState<View>(IDENTITY);
  const [cypher, setCypher] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [, setTick] = useState(0);
  // Auto-framing stays on only until the reader takes over; after that the
  // view is theirs and must not jump around under them.
  const autoFit = useRef(true);

  // d3-force mutates its nodes, so these are built once per map and then
  // written to in place by the simulation.
  const { nodes, links, byId } = useMemo(() => {
    const nodes = buildNodes(map.nodes);
    const byId = new Map(nodes.map((n) => [n.id, n]));
    return { nodes, links: buildLinks(map.edges, new Set(byId.keys())), byId };
  }, [map]);

  /**
   * Frame the whole graph.
   *
   * The forces decide how far apart things end up, which is not knowable in
   * advance, so rather than tuning them until the result happens to fit, the
   * view is fitted to whatever the simulation settles on.
   */
  const fitToView = useCallback(() => {
    if (nodes.length === 0) return;
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const node of nodes) {
      minX = Math.min(minX, node.x - node.r);
      minY = Math.min(minY, node.y - node.r);
      maxX = Math.max(maxX, node.x + node.r);
      maxY = Math.max(maxY, node.y + node.r);
    }

    const pad = 46;
    const width = maxX - minX + pad * 2;
    const height = maxY - minY + pad * 2;
    const whole = Math.min(VIEW_W / width, VIEW_H / height);

    /*
     * On a phone the canvas is around 390 CSS pixels wide while the viewBox is
     * 1000 units, so fitting the entire graph would render captions at about
     * four pixels. Legibility wins over completeness: below that threshold the
     * view zooms to the smallest readable scale and centres on the core idea,
     * and the reader pans or uses the zoom buttons to reach the rest.
     */
    const rendered = svgRef.current?.getBoundingClientRect().width ?? VIEW_W;
    const pixelsPerUnit = rendered / VIEW_W;
    const smallestFont = Math.min(...nodes.map((n) => n.fontSize));
    const legible = 9 / Math.max(0.0001, smallestFont * pixelsPerUnit);

    const k = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Math.max(whole, legible)));

    // When everything no longer fits, keep the paper's central claim in frame.
    const core = nodes.find((n) => n.kind === "core");
    const focusX = k > whole && core ? core.x : (minX + maxX) / 2;
    const focusY = k > whole && core ? core.y : (minY + maxY) / 2;

    setView({ k, x: VIEW_W / 2 - focusX * k, y: VIEW_H / 2 - focusY * k });
  }, [nodes]);

  useEffect(() => {
    const simulation = forceSimulation<SimNode, SimLink>(nodes)
      .force(
        "link",
        forceLink<SimNode, SimLink>(links)
          .id((d) => d.id)
          .distance((l) => {
            const target = l.target as SimNode;
            return 120 + target.r;
          })
          .strength(0.45),
      )
      .force("charge", forceManyBody<SimNode>().strength(-900))
      .force("collide", forceCollide<SimNode>((d) => d.r + 16).strength(0.95))
      // The anchors are what keep role meaningful; see graph.ts.
      .force("anchorX", forceX<SimNode>((d) => d.anchorX).strength(0.08))
      .force("anchorY", forceY<SimNode>((d) => d.anchorY).strength(0.08))
      .on("tick", () => {
        setTick((t) => t + 1);
        // Framed on every tick rather than once at the end: d3 only emits
        // "end" when its timer stops, which a restart can postpone
        // indefinitely, and fitting as it settles keeps the graph in frame
        // throughout the opening animation.
        if (autoFit.current) fitToView();
      });

    simRef.current = simulation;
    return () => {
      simulation.stop();
      simRef.current = null;
    };
  }, [nodes, links, fitToView]);

  // -- coordinate conversion ------------------------------------------------

  const toGraph = useCallback(
    (clientX: number, clientY: number) => {
      const svg = svgRef.current;
      if (!svg) return { x: 0, y: 0 };
      const rect = svg.getBoundingClientRect();
      const scale = VIEW_W / rect.width;
      const vx = (clientX - rect.left) * scale;
      const vy = (clientY - rect.top) * scale;
      return { x: (vx - view.x) / view.k, y: (vy - view.y) / view.k };
    },
    [view],
  );

  // -- dragging -------------------------------------------------------------

  const dragging = useRef<string | null>(null);

  const onNodePointerDown = (event: React.PointerEvent, node: SimNode) => {
    event.stopPropagation();
    (event.target as Element).setPointerCapture?.(event.pointerId);
    dragging.current = node.id;
    autoFit.current = false;
    simRef.current?.alphaTarget(0.25).restart();
  };

  const onNodePointerMove = (event: React.PointerEvent, node: SimNode) => {
    if (dragging.current !== node.id) return;
    const point = toGraph(event.clientX, event.clientY);
    node.fx = point.x;
    node.fy = point.y;
  };

  const onNodePointerUp = (event: React.PointerEvent, node: SimNode) => {
    if (dragging.current !== node.id) return;
    (event.target as Element).releasePointerCapture?.(event.pointerId);
    dragging.current = null;
    // Neo4j leaves a dragged node where you put it; double-click frees it.
    simRef.current?.alphaTarget(0);
  };

  const unpin = (node: SimNode) => {
    if (node.kind === "core") return; // the core stays put, it is the anchor
    node.fx = null;
    node.fy = null;
    simRef.current?.alpha(0.5).restart();
  };

  // -- zoom and pan ---------------------------------------------------------

  const panning = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);

  const onBackgroundPointerDown = (event: React.PointerEvent) => {
    (event.currentTarget as Element).setPointerCapture?.(event.pointerId);
    panning.current = { x: event.clientX, y: event.clientY, vx: view.x, vy: view.y };
    autoFit.current = false;
    setSelected(null);
  };

  const onBackgroundPointerMove = (event: React.PointerEvent) => {
    const start = panning.current;
    if (!start) return;
    const svg = svgRef.current;
    if (!svg) return;
    const scale = VIEW_W / svg.getBoundingClientRect().width;
    setView((current) => ({
      ...current,
      x: start.vx + (event.clientX - start.x) * scale,
      y: start.vy + (event.clientY - start.y) * scale,
    }));
  };

  const onBackgroundPointerUp = () => {
    panning.current = null;
  };

  const zoomBy = useCallback((factor: number, originX?: number, originY?: number) => {
    autoFit.current = false;
    setView((current) => {
      const k = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, current.k * factor));
      if (k === current.k) return current;
      const cx = originX ?? VIEW_W / 2;
      const cy = originY ?? VIEW_H / 2;
      // Keep the point under the cursor fixed while the scale changes.
      return {
        k,
        x: cx - ((cx - current.x) / current.k) * k,
        y: cy - ((cy - current.y) / current.k) * k,
      };
    });
  }, []);

  // Registered natively so the wheel listener can be non-passive and this can
  // zoom without also scrolling the page.
  useEffect(() => {
    const svg = svgRef.current;
    if (!svg) return;
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      const rect = svg.getBoundingClientRect();
      const scale = VIEW_W / rect.width;
      zoomBy(
        event.deltaY < 0 ? 1.12 : 1 / 1.12,
        (event.clientX - rect.left) * scale,
        (event.clientY - rect.top) * scale,
      );
    };
    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => svg.removeEventListener("wheel", onWheel);
  }, [zoomBy]);

  const resetLayout = () => {
    for (const node of nodes) {
      if (node.kind === "core") continue;
      node.fx = null;
      node.fy = null;
    }
    autoFit.current = true; // re-frame as it settles
    simRef.current?.alpha(0.9).restart();
  };

  // -- derived state --------------------------------------------------------

  const active = hovered ?? selected;

  const neighbours = useMemo(() => {
    if (!active) return null;
    const set = new Set<string>([active]);
    for (const link of links) {
      const source = (link.source as SimNode).id ?? (link.source as string);
      const target = (link.target as SimNode).id ?? (link.target as string);
      if (source === active) set.add(target);
      if (target === active) set.add(source);
    }
    return set;
  }, [active, links]);

  const counts = useMemo(() => {
    const out = new Map<NodeKind, number>();
    for (const node of map.nodes) out.set(node.kind, (out.get(node.kind) ?? 0) + 1);
    return out;
  }, [map.nodes]);

  const toggleKind = (kind: NodeKind) =>
    setMuted((current) => {
      const next = new Set(current);
      if (next.has(kind)) next.delete(kind);
      else next.add(kind);
      return next;
    });

  const selectedNode = selected ? byId.get(selected) : undefined;

  const relationships = useMemo<Relationship[]>(() => {
    if (!selected) return [];
    return links.flatMap<Relationship>((link) => {
      const source = link.source as SimNode;
      const target = link.target as SimNode;
      if (source.id === selected) {
        return [{ dir: "out", type: link.label, other: target }];
      }
      if (target.id === selected) {
        return [{ dir: "in", type: link.label, other: source }];
      }
      return [];
    });
  }, [selected, links]);

  const isDimmed = (node: SimNode) =>
    muted.has(node.kind) || (neighbours !== null && !neighbours.has(node.id));

  return (
    <div className="graph">
      <div className="graph-toolbar">
        <div className="graph-labels">
          {[...counts.entries()].map(([kind, count]) => (
            <button
              key={kind}
              className={`label-chip${muted.has(kind) ? " is-muted" : ""}`}
              style={{ ["--chip" as string]: KIND_COLOR[kind] }}
              onClick={() => toggleKind(kind)}
              title={muted.has(kind) ? `Show ${KIND_LABEL[kind]}` : `Hide ${KIND_LABEL[kind]}`}
            >
              <i />
              {KIND_LABEL[kind]}
              <b>{count}</b>
            </button>
          ))}
        </div>

        <div className="graph-controls">
          <button onClick={() => zoomBy(1.25)} aria-label="Zoom in" title="Zoom in">
            +
          </button>
          <button onClick={() => zoomBy(1 / 1.25)} aria-label="Zoom out" title="Zoom out">
            −
          </button>
          <button onClick={resetLayout} title="Re-run the layout and unpin every node">
            Reset
          </button>
          <button
            onClick={async () => {
              try {
                setCypher(await exportCypher(map, title));
              } catch (caught) {
                setCypher(
                  `// Could not build the export: ${
                    caught instanceof Error ? caught.message : "unknown error"
                  }`,
                );
              }
            }}
            title="Render this graph as Cypher for Neo4j"
          >
            Cypher
          </button>
        </div>
      </div>

      <svg
        ref={svgRef}
        className="graph-canvas"
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        role="img"
        aria-label={`Graph of the paper's argument. Core idea: ${map.core}. ${map.nodes.length} nodes, ${links.length} relationships.`}
      >
        <defs>
          <marker
            id="pp-arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 9 5 L 0 9 z" className="arrow-head" />
          </marker>
          <marker
            id="pp-arrow-lit"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M 0 1 L 9 5 L 0 9 z" className="arrow-head is-lit" />
          </marker>
        </defs>

        <rect
          className="graph-backdrop"
          width={VIEW_W}
          height={VIEW_H}
          onPointerDown={onBackgroundPointerDown}
          onPointerMove={onBackgroundPointerMove}
          onPointerUp={onBackgroundPointerUp}
          onPointerCancel={onBackgroundPointerUp}
        />

        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
          <g className="graph-links">
            {links.map((link, index) => {
              const source = link.source as SimNode;
              const target = link.target as SimNode;
              if (typeof source === "string" || typeof target === "string") return null;

              const geometry = linkGeometry(source, target, link.twin);
              if (!geometry) return null;

              const lit =
                active !== null && (source.id === active || target.id === active);
              const dim =
                muted.has(source.kind) ||
                muted.has(target.kind) ||
                (active !== null && !lit);

              return (
                <g
                  key={`${source.id}-${target.id}-${index}`}
                  className={`link${lit ? " is-lit" : ""}${dim ? " is-dim" : ""}`}
                >
                  <path
                    d={geometry.path}
                    markerEnd={`url(#${lit ? "pp-arrow-lit" : "pp-arrow"})`}
                  />
                  <rect
                    className="link-plate"
                    x={geometry.labelX - (link.label.length * 5.4 + 12) / 2}
                    y={geometry.labelY - 8}
                    width={link.label.length * 5.4 + 12}
                    height={16}
                    rx={8}
                  />
                  <text x={geometry.labelX} y={geometry.labelY + 3.5}>
                    {link.label}
                  </text>
                </g>
              );
            })}
          </g>

          <g className="graph-nodes">
            {nodes.map((node) => {
              const dim = isDimmed(node);
              const pinned = node.fx != null && node.kind !== "core";

              return (
                <g
                  key={node.id}
                  className={`node${node.id === selected ? " is-selected" : ""}${dim ? " is-dim" : ""}`}
                  transform={`translate(${node.x} ${node.y})`}
                  tabIndex={0}
                  role="button"
                  aria-pressed={node.id === selected}
                  aria-label={`${node.label}. ${KIND_LABEL[node.kind]}. ${node.blurb}`}
                  onPointerDown={(event) => onNodePointerDown(event, node)}
                  onPointerMove={(event) => onNodePointerMove(event, node)}
                  onPointerUp={(event) => onNodePointerUp(event, node)}
                  onPointerEnter={() => setHovered(node.id)}
                  onPointerLeave={() => setHovered(null)}
                  onClick={() => setSelected(node.id === selected ? null : node.id)}
                  onDoubleClick={() => unpin(node)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSelected(node.id === selected ? null : node.id);
                    }
                  }}
                >
                  <circle
                    className="node-ring"
                    r={node.r + 5}
                    style={{ stroke: KIND_COLOR[node.kind] }}
                  />
                  <circle
                    className="node-body"
                    r={node.r}
                    style={{ fill: KIND_COLOR[node.kind] }}
                  />
                  <text
                    className="node-caption"
                    fontSize={node.fontSize}
                    y={node.lines.length === 1 ? node.fontSize * 0.35 : -node.fontSize * 0.15}
                  >
                    {node.lines.map((line, index) => (
                      <tspan key={index} x={0} dy={index === 0 ? 0 : node.fontSize * 1.15}>
                        {line}
                      </tspan>
                    ))}
                  </text>
                  {pinned && (
                    <circle className="node-pin" cx={node.r * 0.72} cy={-node.r * 0.72} r={4} />
                  )}
                </g>
              );
            })}
          </g>
        </g>
      </svg>

      {cypher !== null && (
        <div
          className="cypher-overlay"
          role="dialog"
          aria-modal="true"
          aria-label="Cypher export"
          onClick={(event) => {
            if (event.target === event.currentTarget) setCypher(null);
          }}
        >
          <div className="cypher-sheet">
            <header>
              <h4>Load this graph into Neo4j</h4>
              <button className="chip" onClick={() => setCypher(null)}>
                Close
              </button>
            </header>
            <p className="depth-note" style={{ marginTop: 0 }}>
              Paste into Neo4j Browser or pipe through cypher-shell.
            </p>
            <pre>{cypher}</pre>
            <button
              className="primary"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(cypher);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1800);
                } catch {
                  setCopied(false);
                }
              }}
            >
              {copied ? "Copied" : "Copy"}
            </button>
          </div>
        </div>
      )}

      <div className="inspector" aria-live="polite">
        {selectedNode ? (
          <>
            <div className="inspector-head">
              <span
                className="label-chip is-static"
                style={{ ["--chip" as string]: KIND_COLOR[selectedNode.kind] }}
              >
                <i />
                {KIND_LABEL[selectedNode.kind]}
              </span>
              <h4>{selectedNode.label}</h4>
            </div>

            <dl className="properties">
              <div>
                <dt>id</dt>
                <dd className="mono">{selectedNode.id}</dd>
              </div>
              <div>
                <dt>weight</dt>
                <dd className="mono">{selectedNode.weight.toFixed(2)}</dd>
              </div>
              <div className="wide">
                <dt>summary</dt>
                <dd>{selectedNode.blurb}</dd>
              </div>
            </dl>

            {relationships.length > 0 && (
              <div className="rel-list">
                {relationships.map((relationship, index) => (
                  <span className="rel" key={index}>
                    {relationship.dir === "out" ? (
                      <>
                        <em>-[:{relationship.type.toUpperCase().replace(/\s+/g, "_")}]-&gt;</em>
                        <b style={{ color: KIND_COLOR[relationship.other.kind] }}>
                          {relationship.other.label}
                        </b>
                      </>
                    ) : (
                      <>
                        <b style={{ color: KIND_COLOR[relationship.other.kind] }}>
                          {relationship.other.label}
                        </b>
                        <em>-[:{relationship.type.toUpperCase().replace(/\s+/g, "_")}]-&gt;</em>
                      </>
                    )}
                  </span>
                ))}
              </div>
            )}
          </>
        ) : (
          <p className="inspector-hint">
            <strong>{map.core}</strong> — select a node to inspect it, drag to move
            it, double-click to release one you have moved. Drag the background to pan,
            zoom with the + and − buttons or a scroll wheel, and use the labels above to
            hide a category.
          </p>
        )}
      </div>
    </div>
  );
}
