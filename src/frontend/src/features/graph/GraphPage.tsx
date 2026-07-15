// Scene Graph (doc 06 §6) — the book's story-shape view. Full-bleed D3-zoom canvas
// (pan/zoom only; no node dragging, nothing persisted). Single-click a node → Scene
// Modal (edit); double-click → the editor. ＋ Add scene / ⤢ Fit float over the canvas.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import * as d3 from "d3";

import { Button } from "../../components/ui";
import { useScenes } from "../../queries/scenes";
import { SceneModal } from "../sceneModal/SceneModal";
import { computeLayout, NODE_H, NODE_W, type LayoutNode } from "./layout";

function truncate(text: string, max = 22) {
  return text.length > max ? text.slice(0, max - 1) + "…" : text;
}

// Point where the segment center(from)→center(to) meets the target node's border,
// so arrowheads land on the box edge rather than under it.
function borderPoint(from: LayoutNode, to: LayoutNode) {
  const fx = from.x + NODE_W / 2;
  const fy = from.y + NODE_H / 2;
  const tx = to.x + NODE_W / 2;
  const ty = to.y + NODE_H / 2;
  const dx = fx - tx;
  const dy = fy - ty;
  const hw = NODE_W / 2 + 4;
  const hh = NODE_H / 2 + 4;
  if (dx === 0 && dy === 0) return { x: tx, y: ty };
  const scale = 1 / Math.max(Math.abs(dx) / hw, Math.abs(dy) / hh);
  return { x: tx + dx * scale, y: ty + dy * scale };
}

export default function GraphPage() {
  const { bookId = "" } = useParams();
  const navigate = useNavigate();
  const { data, isLoading } = useScenes(bookId);
  const scenes = data?.scenes ?? [];
  const relationships = data?.relationships ?? [];

  const layout = useMemo(() => computeLayout(scenes, relationships), [scenes, relationships]);

  const svgRef = useRef<SVGSVGElement>(null);
  const zoomRef = useRef<d3.ZoomBehavior<SVGSVGElement, unknown> | null>(null);
  const [transform, setTransform] = useState(d3.zoomIdentity);
  const clickTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fittedRef = useRef(false);

  const [modal, setModal] = useState<{ sceneId: string | null } | null>(null);

  const fit = useCallback(() => {
    const svg = svgRef.current;
    const zoom = zoomRef.current;
    if (!svg || !zoom) return;
    const { clientWidth: w, clientHeight: h } = svg;
    const scale = Math.min(w / layout.width, h / layout.height, 1.1) * 0.92;
    const tx = (w - layout.width * scale) / 2;
    const ty = Math.max(24, (h - layout.height * scale) / 2);
    d3.select(svg).transition().duration(250).call(zoom.transform, d3.zoomIdentity.translate(tx, ty).scale(scale));
  }, [layout.width, layout.height]);

  useEffect(() => {
    const svg = d3.select(svgRef.current!);
    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 2])
      .on("zoom", (e) => setTransform(e.transform));
    zoomRef.current = zoom;
    svg.call(zoom).on("dblclick.zoom", null);
    return () => {
      svg.on(".zoom", null);
    };
  }, []);

  // Fit once when scenes first arrive.
  useEffect(() => {
    if (!fittedRef.current && !isLoading && layout.nodes.length > 0) {
      fittedRef.current = true;
      fit();
    }
  }, [isLoading, layout.nodes.length, fit]);

  const onNodeClick = (node: LayoutNode) => {
    if (node.isSentinel) return;
    if (clickTimer.current) clearTimeout(clickTimer.current);
    clickTimer.current = setTimeout(() => setModal({ sceneId: node.id }), 220);
  };
  const onNodeDblClick = (node: LayoutNode) => {
    if (node.isSentinel) return;
    if (clickTimer.current) clearTimeout(clickTimer.current);
    navigate(`/book/${bookId}/scene/${node.id}`);
  };

  const activeCount = scenes.filter((s) => s.status === "active").length;

  return (
    <div className="relative h-full w-full overflow-hidden bg-paper">
      <svg ref={svgRef} className="h-full w-full">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="var(--accent)" />
          </marker>
          <marker id="arrow-soft" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="var(--edge-soft)" />
          </marker>
        </defs>

        <g transform={`translate(${transform.x},${transform.y}) scale(${transform.k})`}>
          {/* edges under nodes */}
          {layout.edges.map((e) => {
            const from = layout.nodes.find((n) => n.id === e.from);
            const to = layout.nodes.find((n) => n.id === e.to);
            if (!from || !to) return null;
            const start = borderPoint(to, from);
            const end = borderPoint(from, to);
            return (
              <line
                key={e.id}
                x1={start.x}
                y1={start.y}
                x2={end.x}
                y2={end.y}
                stroke={e.soft ? "var(--edge-soft)" : "var(--accent)"}
                strokeWidth={e.soft ? 1.5 : 1.5}
                strokeDasharray={e.soft ? "4 4" : undefined}
                markerEnd={e.arrow ? (e.soft ? "url(#arrow-soft)" : "url(#arrow)") : undefined}
              >
                {e.label && <title>{e.label}</title>}
              </line>
            );
          })}

          {/* nodes */}
          {layout.nodes.map((n) => {
            if (n.isSentinel) {
              return (
                <g key={n.id} transform={`translate(${n.x},${n.y})`}>
                  <rect
                    width={NODE_W}
                    height={NODE_H}
                    rx={NODE_H / 2}
                    fill="var(--paper)"
                    stroke="var(--ink-soft)"
                    strokeWidth={1}
                  />
                  <text x={NODE_W / 2} y={NODE_H / 2 + 4} textAnchor="middle" fontSize="13" fill="var(--ink-soft)">
                    {n.title}
                  </text>
                </g>
              );
            }
            return (
              <g
                key={n.id}
                transform={`translate(${n.x},${n.y})`}
                className="cursor-pointer"
                onClick={() => onNodeClick(n)}
                onDoubleClick={() => onNodeDblClick(n)}
              >
                <rect
                  width={NODE_W}
                  height={NODE_H}
                  rx={8}
                  fill="var(--surface)"
                  stroke="var(--line)"
                  strokeWidth={1}
                />
                <text x={12} y={NODE_H / 2 + 4} fontSize="13.5" fill="var(--ink)">
                  {n.seq != null && <tspan fill="var(--ink-soft)">#{n.seq} </tspan>}
                  {truncate(n.title, n.seq != null ? 18 : 22)}
                </text>
                <title>{n.description || n.title}</title>
              </g>
            );
          })}
        </g>
      </svg>

      {/* Empty state */}
      {!isLoading && activeCount === 0 && (
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-3">
          <p className="text-[0.9375rem] text-ink-soft">No scenes yet.</p>
          <div className="pointer-events-auto">
            <Button variant="primary" onClick={() => setModal({ sceneId: null })}>
              Add scene
            </Button>
          </div>
        </div>
      )}

      {/* Floating controls */}
      <div className="absolute bottom-6 right-6 flex items-center gap-2">
        <Button variant="secondary" onClick={fit} title="Fit to view">
          ⤢ Fit
        </Button>
        <Button variant="primary" onClick={() => setModal({ sceneId: null })}>
          ＋ Add scene
        </Button>
      </div>

      {modal && (
        <SceneModal
          bookId={bookId}
          sceneId={modal.sceneId}
          onClose={() => setModal(null)}
          onSaved={(scene) => {
            // On create, keep the modal flow snappy; the cache patch redraws the node.
            void scene;
          }}
        />
      )}
    </div>
  );
}
