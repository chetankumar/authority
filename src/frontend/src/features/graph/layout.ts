// Pure, deterministic graph layout (doc 06 §6): same data → same picture, nothing
// persisted. Trunk is a vertical column top→bottom (Start pinned top, The End at the
// trunk's foot); unanchored hard chains sit in a right column; soft-only scenes in a
// left column (their soft edges show the anchor); orphans in a bottom row.
import { END_ID, START_ID, type Scene, type SoftRelationship } from "../../api/scenes";

export const NODE_W = 168;
export const NODE_H = 46;
const ROW_H = 92;
const COL_GAP = 240;
const CENTER_X = 320;
const TOP_Y = 32;

export interface LayoutNode {
  id: string;
  x: number; // top-left
  y: number;
  title: string;
  description?: string;
  isSentinel: boolean;
  placement?: Scene["placement"];
}

export interface LayoutEdge {
  id: string;
  from: string;
  to: string;
  soft: boolean;
  arrow: boolean; // false for "around"
  label?: string;
}

export interface Layout {
  nodes: LayoutNode[];
  edges: LayoutEdge[];
  width: number;
  height: number;
}

const centerOf = (n: LayoutNode) => ({ cx: n.x + NODE_W / 2, cy: n.y + NODE_H / 2 });

export function computeLayout(scenes: Scene[], relationships: SoftRelationship[]): Layout {
  const active = scenes.filter((s) => s.status === "active");
  const byId = new Map(active.map((s) => [s.id, s]));
  const nodes: LayoutNode[] = [];
  const place = (id: string, x: number, y: number, s?: Scene, sentinel = false) =>
    nodes.push({
      id,
      x,
      y,
      title: sentinel ? (id === START_ID ? "Start" : "The End") : s!.title,
      description: s?.description,
      isSentinel: sentinel,
      placement: s?.placement,
    });

  const of = (p: Scene["placement"]) => active.filter((s) => s.placement === p).sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0));
  const trunk = of("trunk");
  const unanchored = of("unanchored");
  const floating = of("floating");
  const orphan = of("orphan");

  // Trunk column (center), Start pinned top, The End at the foot.
  place(START_ID, CENTER_X, TOP_Y, undefined, true);
  let y = TOP_Y + ROW_H;
  for (const s of trunk) {
    place(s.id, CENTER_X, y, s);
    y += ROW_H;
  }
  const endY = y;
  place(END_ID, CENTER_X, endY, undefined, true);

  // Unanchored chains — right column.
  let uy = TOP_Y + ROW_H;
  for (const s of unanchored) {
    place(s.id, CENTER_X + COL_GAP, uy, s);
    uy += ROW_H;
  }

  // Floating — left column.
  let fy = TOP_Y + ROW_H;
  for (const s of floating) {
    place(s.id, CENTER_X - COL_GAP, fy, s);
    fy += ROW_H;
  }

  // Orphans — bottom row.
  const bottomY = Math.max(endY, uy, fy) + ROW_H;
  orphan.forEach((s, i) => place(s.id, CENTER_X - COL_GAP + i * (NODE_W + 32), bottomY, s));

  const nodeById = new Map(nodes.map((n) => [n.id, n]));
  const edges: LayoutEdge[] = [];

  // Hard chain: draw prev → scene wherever both endpoints are placed (sentinels included).
  for (const s of active) {
    if (s.previousSceneId && nodeById.has(s.previousSceneId)) {
      edges.push({ id: `h-${s.previousSceneId}-${s.id}`, from: s.previousSceneId, to: s.id, soft: false, arrow: true });
    }
    if (s.nextSceneId === END_ID && nodeById.has(END_ID)) {
      edges.push({ id: `h-${s.id}-END`, from: s.id, to: END_ID, soft: false, arrow: true });
    }
  }

  // Soft edges (dotted; "around" has no arrowhead).
  // "before" = fromScene comes before toScene → arrow from → to.
  // "after"  = fromScene comes after toScene  → arrow to → from (reversed).
  for (const r of relationships) {
    if (byId.has(r.fromSceneId) && byId.has(r.toSceneId)) {
      const reversed = r.type === "after";
      edges.push({
        id: r.id,
        from: reversed ? r.toSceneId : r.fromSceneId,
        to: reversed ? r.fromSceneId : r.toSceneId,
        soft: true,
        arrow: r.type !== "around",
        label: `definitely ${r.type} ${byId.get(r.toSceneId)!.title}`,
      });
    }
  }

  const maxX = Math.max(...nodes.map((n) => n.x + NODE_W), CENTER_X + COL_GAP + NODE_W);
  const maxY = Math.max(...nodes.map((n) => n.y + NODE_H), bottomY + NODE_H);
  void centerOf; // centers computed in the renderer where node sizes are known
  return { nodes, edges, width: maxX + 80, height: maxY + 80 };
}
