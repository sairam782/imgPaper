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

import type { NodeLabel, PaperGraph } from "../types";
import {
  buildLinks,
  buildNodes,
  FAMILY,
  LABEL_ORDER,
  linkGeometry,
  VIEW_H,
  VIEW_W,
  type SimLink,
  type SimNode,
} from "./graph";

const MIN_ZOOM = 0.3;
const MAX_ZOOM = 3;

interface View {
  k: number;
  x: number;
  y: number;
}

interface Relationship {
  dir: "in" | "out";
  type: string;
  other: SimNode;
  derived: boolean;
}

export default function GraphView({
  graph,
  onExport,
}: {
  graph: PaperGraph;
  onExport: () => void;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const simRef = useRef<Simulation<SimNode, SimLink> | null>(null);
  const autoFit = useRef(true);

  const [selected, setSelected] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [muted, setMuted] = useState<Set<NodeLabel>>(() => new Set(graph.quiet));
  const [query, setQuery] = useState("");
  const [view, setView] = useState<View>({ k: 1, x: 0, y: 0 });
  const [, setTick] = useState(0);

  /*
   * Hiding a label takes its nodes out of the simulation rather than just
   * fading them. Left in, they keep pushing on everything else, so the graph
   * stays as sprawling as it was and hiding buys the reader nothing.
   */
  const { nodes, links, byId } = useMemo(() => {
    const kept = graph.nodes.filter((n) => !muted.has(n.kind));
    const nodes = buildNodes(kept);
    const byId = new Map(nodes.map((n) => [n.id, n]));
    return { nodes, links: buildLinks(graph.edges, new Set(byId.keys())), byId };
  }, [graph, muted]);

  const fitToView = useCallback(() => {
    const framed = nodes;
    if (!framed.length) return;

    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const node of framed) {
      minX = Math.min(minX, node.x - node.r);
      minY = Math.min(minY, node.y - node.r);
      maxX = Math.max(maxX, node.x + node.r);
      maxY = Math.max(maxY, node.y + node.r);
    }

    const pad = 40;
    const whole = Math.min(
      VIEW_W / (maxX - minX + pad * 2),
      VIEW_H / (maxY - minY + pad * 2),
    );

    /*
     * Always frame the whole graph, on every screen.
     *
     * An earlier version zoomed in on narrow screens so captions stayed
     * readable. That suited a dozen nodes; at sixty it put five on screen and
     * silently hid the rest, which is worse than small text — the reader
     * cannot tell there is more. Fitting always shows the shape, the clusters
     * and the colours, and reading is done by tapping a node, which opens the
     * inspector with its full text, or by zooming in.
     */
    const k = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, whole));

    setView({
      k,
      x: VIEW_W / 2 - ((minX + maxX) / 2) * k,
      y: VIEW_H / 2 - ((minY + maxY) / 2) * k,
    });
  }, [nodes]);

  useEffect(() => {
    const simulation = forceSimulation<SimNode, SimLink>(nodes)
      .force(
        "link",
        forceLink<SimNode, SimLink>(links)
          .id((d) => d.id)
          .distance((l) => 70 + (l.target as SimNode).r)
          .strength(0.35),
      )
      .force("charge", forceManyBody<SimNode>().strength(-620))
      .force("collide", forceCollide<SimNode>((d) => d.r + 9).strength(0.95))
      .force("anchorX", forceX<SimNode>((d) => d.anchorX).strength(0.12))
      .force("anchorY", forceY<SimNode>((d) => d.anchorY).strength(0.12))
      .on("tick", () => {
        setTick((t) => t + 1);
        if (autoFit.current) fitToView();
      });

    simRef.current = simulation;
    return () => {
      simulation.stop();
      simRef.current = null;
    };
  }, [nodes, links, fitToView]);

  const toGraph = useCallback(
    (clientX: number, clientY: number) => {
      const svg = svgRef.current;
      if (!svg) return { x: 0, y: 0 };
      const rect = svg.getBoundingClientRect();
      const scale = VIEW_W / rect.width;
      return {
        x: ((clientX - rect.left) * scale - view.x) / view.k,
        y: ((clientY - rect.top) * scale - view.y) / view.k,
      };
    },
    [view],
  );

  // -- interaction ----------------------------------------------------------

  const dragging = useRef<string | null>(null);

  const onNodeDown = (event: React.PointerEvent, node: SimNode) => {
    event.stopPropagation();
    (event.target as Element).setPointerCapture?.(event.pointerId);
    dragging.current = node.id;
    autoFit.current = false;
    simRef.current?.alphaTarget(0.2).restart();
  };

  const onNodeMove = (event: React.PointerEvent, node: SimNode) => {
    if (dragging.current !== node.id) return;
    const point = toGraph(event.clientX, event.clientY);
    node.fx = point.x;
    node.fy = point.y;
  };

  const onNodeUp = (event: React.PointerEvent, node: SimNode) => {
    if (dragging.current !== node.id) return;
    (event.target as Element).releasePointerCapture?.(event.pointerId);
    dragging.current = null;
    simRef.current?.alphaTarget(0);
  };

  const unpin = (node: SimNode) => {
    if (node.kind === "Paper") return;
    node.fx = null;
    node.fy = null;
    simRef.current?.alpha(0.4).restart();
  };

  const panning = useRef<{ x: number; y: number; vx: number; vy: number } | null>(null);

  const onBackDown = (event: React.PointerEvent) => {
    (event.currentTarget as Element).setPointerCapture?.(event.pointerId);
    panning.current = { x: event.clientX, y: event.clientY, vx: view.x, vy: view.y };
    autoFit.current = false;
    setSelected(null);
  };

  const onBackMove = (event: React.PointerEvent) => {
    const start = panning.current;
    const svg = svgRef.current;
    if (!start || !svg) return;
    const scale = VIEW_W / svg.getBoundingClientRect().width;
    setView((current) => ({
      ...current,
      x: start.vx + (event.clientX - start.x) * scale,
      y: start.vy + (event.clientY - start.y) * scale,
    }));
  };

  const zoomBy = useCallback((factor: number, originX?: number, originY?: number) => {
    autoFit.current = false;
    setView((current) => {
      const k = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, current.k * factor));
      if (k === current.k) return current;
      const cx = originX ?? VIEW_W / 2;
      const cy = originY ?? VIEW_H / 2;
      return {
        k,
        x: cx - ((cx - current.x) / current.k) * k,
        y: cy - ((cy - current.y) / current.k) * k,
      };
    });
  }, []);

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
      if (node.kind === "Paper") continue;
      node.fx = null;
      node.fy = null;
    }
    autoFit.current = true;
    simRef.current?.alpha(0.9).restart();
  };

  // -- derived --------------------------------------------------------------

  const active = hovered ?? selected;

  const neighbours = useMemo(() => {
    if (!active) return null;
    const set = new Set<string>([active]);
    for (const link of links) {
      const source = (link.source as SimNode).id;
      const target = (link.target as SimNode).id;
      if (source === active) set.add(target);
      if (target === active) set.add(source);
    }
    return set;
  }, [active, links]);

  const matches = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return null;
    return new Set(
      nodes
        .filter(
          (n) =>
            n.label.toLowerCase().includes(needle) ||
            n.blurb.toLowerCase().includes(needle),
        )
        .map((n) => n.id),
    );
  }, [query, nodes]);

  const selectedNode = selected ? byId.get(selected) : undefined;

  const relationships = useMemo<Relationship[]>(() => {
    if (!selected) return [];
    return links.flatMap<Relationship>((link) => {
      const source = link.source as SimNode;
      const target = link.target as SimNode;
      if (source.id === selected) {
        return [{ dir: "out", type: link.type, other: target, derived: link.derived }];
      }
      if (target.id === selected) {
        return [{ dir: "in", type: link.type, other: source, derived: link.derived }];
      }
      return [];
    });
  }, [selected, links]);

  const dimmed = (node: SimNode) =>
    (matches !== null && !matches.has(node.id)) ||
    (neighbours !== null && !neighbours.has(node.id));

  const toggleLabel = (kind: NodeLabel) => {
    autoFit.current = true;
    setMuted((current) => {
      const next = new Set(current);
      if (next.has(kind)) next.delete(kind);
      else next.add(kind);
      return next;
    });
    simRef.current?.alpha(0.3).restart();
  };

  const present = LABEL_ORDER.filter((label) => graph.counts[label]);

  return (
    <div className="graph">
      <div className="graph-toolbar">
        <div className="graph-labels">
          {present.map((kind) => {
            const family = FAMILY[kind];
            return (
              <button
                key={kind}
                className={`label-chip${muted.has(kind) ? " is-muted" : ""}${
                  family.solid ? "" : " is-hollow"
                }`}
                style={{ ["--chip" as string]: family.hue }}
                onClick={() => toggleLabel(kind)}
                title={`${muted.has(kind) ? "Show" : "Hide"} ${kind} nodes`}
              >
                <i />
                {kind}
                <b>{graph.counts[kind]}</b>
              </button>
            );
          })}
        </div>

        <div className="graph-controls">
          <input
            className="graph-search"
            type="search"
            value={query}
            placeholder="Find…"
            aria-label="Find a node"
            onChange={(event) => setQuery(event.target.value)}
          />
          <button onClick={() => zoomBy(1.25)} aria-label="Zoom in" title="Zoom in">
            +
          </button>
          <button onClick={() => zoomBy(1 / 1.25)} aria-label="Zoom out" title="Zoom out">
            −
          </button>
          <button onClick={resetLayout} title="Re-run the layout and unpin every node">
            Reset
          </button>
          <button onClick={onExport} title="Render this graph as Cypher for Neo4j">
            Cypher
          </button>
        </div>
      </div>

      <svg
        ref={svgRef}
        className="graph-canvas"
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        role="img"
        aria-label={`Graph of the paper. ${graph.nodes.length} nodes and ${graph.edges.length} relationships across ${present.length} labels.`}
      >
        <defs>
          <marker id="pp-arrow" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1 L 9 5 L 0 9 z" className="arrow-head" />
          </marker>
          <marker id="pp-arrow-lit" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 1 L 9 5 L 0 9 z" className="arrow-head is-lit" />
          </marker>
        </defs>

        <rect
          className="graph-backdrop"
          width={VIEW_W}
          height={VIEW_H}
          onPointerDown={onBackDown}
          onPointerMove={onBackMove}
          onPointerUp={() => (panning.current = null)}
          onPointerCancel={() => (panning.current = null)}
        />

        <g transform={`translate(${view.x} ${view.y}) scale(${view.k})`}>
          <g className="graph-links">
            {links.map((link, index) => {
              const source = link.source as SimNode;
              const target = link.target as SimNode;
              if (typeof source === "string" || typeof target === "string") return null;

              const geometry = linkGeometry(source, target, link.twin);
              if (!geometry) return null;

              const lit = active !== null && (source.id === active || target.id === active);
              const hide =
                (active !== null && !lit) ||
                (matches !== null && !(matches.has(source.id) && matches.has(target.id)));

              // At a distance every label is noise; show them where the reader
              // is looking, or once the view is zoomed in far enough to read.
              const showLabel = lit || (view.k > 1.15 && active === null && !hide);

              return (
                <g
                  key={`${source.id}-${target.id}-${index}`}
                  className={`link${lit ? " is-lit" : ""}${hide ? " is-dim" : ""}${
                    link.derived ? " is-derived" : ""
                  }`}
                >
                  <path d={geometry.path} markerEnd={`url(#${lit ? "pp-arrow-lit" : "pp-arrow"})`} />
                  {showLabel && (
                    <>
                      <rect
                        className="link-plate"
                        x={geometry.labelX - (link.label.length * 5 + 10) / 2}
                        y={geometry.labelY - 7.5}
                        width={link.label.length * 5 + 10}
                        height={15}
                        rx={7}
                      />
                      <text x={geometry.labelX} y={geometry.labelY + 3}>
                        {link.label}
                      </text>
                    </>
                  )}
                </g>
              );
            })}
          </g>

          <g className="graph-nodes">
            {nodes.map((node) => {
              const family = FAMILY[node.kind];
              const pinned = node.fx != null && node.kind !== "Paper";
              return (
                <g
                  key={node.id}
                  className={`node${node.id === selected ? " is-selected" : ""}${
                    dimmed(node) ? " is-dim" : ""
                  }${family.solid ? "" : " is-hollow"}`}
                  style={{ ["--hue" as string]: family.hue }}
                  transform={`translate(${node.x} ${node.y})`}
                  tabIndex={0}
                  role="button"
                  aria-pressed={node.id === selected}
                  aria-label={`${node.label}. ${node.kind}. ${node.blurb}`}
                  onPointerDown={(event) => onNodeDown(event, node)}
                  onPointerMove={(event) => onNodeMove(event, node)}
                  onPointerUp={(event) => onNodeUp(event, node)}
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
                  {/* Small nodes cannot fit a long caption, so the full text
                      is always one hover away. */}
                  <title>{`${node.label} — ${node.kind}${node.blurb ? `\n${node.blurb}` : ""}`}</title>
                  <circle className="node-ring" r={node.r + 4} />
                  <circle className="node-body" r={node.r} />
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
                  {pinned && <circle className="node-pin" cx={node.r * 0.7} cy={-node.r * 0.7} r={3.5} />}
                </g>
              );
            })}
          </g>
        </g>
      </svg>

      <div className="inspector" aria-live="polite">
        {selectedNode ? (
          <>
            <div className="inspector-head">
              <span
                className={`label-chip is-static${FAMILY[selectedNode.kind].solid ? "" : " is-hollow"}`}
                style={{ ["--chip" as string]: FAMILY[selectedNode.kind].hue }}
              >
                <i />
                {selectedNode.kind}
              </span>
              <h4>{selectedNode.label}</h4>
              <span className="degree">{selectedNode.degree} relationships</span>
            </div>

            {selectedNode.blurb && <p className="inspector-blurb">{selectedNode.blurb}</p>}

            {Object.keys(selectedNode.props).length > 0 && (
              <dl className="properties">
                {Object.entries(selectedNode.props).map(([key, value]) => (
                  <div key={key} className={value.length > 40 ? "wide" : undefined}>
                    <dt>{key}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
            )}

            {relationships.length > 0 && (
              <div className="rel-list">
                {relationships.map((relationship, index) => (
                  <button
                    className={`rel${relationship.derived ? " is-derived" : ""}`}
                    key={index}
                    onClick={() => setSelected(relationship.other.id)}
                    title={`Go to ${relationship.other.label}`}
                  >
                    {relationship.dir === "out" ? (
                      <>
                        <em>-[:{relationship.type}]-&gt;</em>
                        <b style={{ color: FAMILY[relationship.other.kind].hue }}>
                          {relationship.other.label}
                        </b>
                      </>
                    ) : (
                      <>
                        <b style={{ color: FAMILY[relationship.other.kind].hue }}>
                          {relationship.other.label}
                        </b>
                        <em>-[:{relationship.type}]-&gt;</em>
                      </>
                    )}
                  </button>
                ))}
              </div>
            )}
          </>
        ) : (
          <p className="inspector-hint">
            {graph.nodes.length} nodes and {graph.edges.length} relationships, every one
            of them drawn from the digest. Select a node to inspect it and walk its
            connections, drag to move it, double-click to release it. Labels above toggle
            whole categories — three start hidden so the first look is readable.
          </p>
        )}
      </div>
    </div>
  );
}
