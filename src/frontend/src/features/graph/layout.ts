// Pure, deterministic graph layout (doc 06 §6): same data → same picture, nothing
// persisted. Trunk shards horizontally (10 scenes per column, top→bottom then right);
// Start pinned top of column 0, The End below the last trunk scene in its column.
// Unanchored hard chains sit in a right column; soft-only scenes in a left column
// (their soft edges show the anchor); orphans in a bottom row.
import { END_ID, START_ID, type Scene, type SoftRelationship } from "../../api/scenes";

export const NODE_W = 168;
export const NODE_H = 46;
export const ROW_H = 92;
const COL_GAP = 240;
const CENTER_X = 320;
const TOP_Y = 32;
const NODES_PER_COLUMN = 10;
const SHARD_COL_W = NODE_W + 32;

export interface LayoutNode {
  id: string;
  x: number; // top-left
  y: number;
  title: string;
  description?: string;
  isSentinel: boolean;
  placement?: Scene["placement"];
  seq: number | null;
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

type PlaceFn = (id: string, x: number, y: number, s?: Scene, sentinel?: boolean) => void;

const centerOf = (n: LayoutNode) => ({ cx: n.x + NODE_W / 2, cy: n.y + NODE_H / 2 });

function placeTrunkSharded(
  scenes: Scene[],
  baseX: number,
  startY: number,
  place: PlaceFn,
): { lastCol: number; maxY: number } {
  let maxY = startY;
  scenes.forEach((s, i) => {
    const col = Math.floor(i / NODES_PER_COLUMN);
    const row = i % NODES_PER_COLUMN;
    const x = baseX + col * SHARD_COL_W;
    const y = startY + row * ROW_H;
    place(s.id, x, y, s);
    maxY = Math.max(maxY, y);
  });
  const lastCol = scenes.length === 0 ? 0 : Math.floor((scenes.length - 1) / NODES_PER_COLUMN);
  return { lastCol, maxY };
}

export function computeLayout(scenes: Scene[], relationships: SoftRelationship[]): Layout {
  const active = scenes.filter((s) => s.status === "active");
  const byId = new Map(active.map((s) => [s.id, s]));
  const nodes: LayoutNode[] = [];
  const place: PlaceFn = (id, x, y, s, sentinel = false) =>
    nodes.push({
      id,
      x,
      y,
      title: sentinel ? (id === START_ID ? "Start" : "The End") : s!.title,
      description: s?.description,
      isSentinel: sentinel,
      placement: s?.placement,
      seq: s?.seq ?? null,
    });

  const of = (p: Scene["placement"]) => active.filter((s) => s.placement === p).sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0));
  const trunk = of("trunk");
  const unanchored = of("unanchored");
  const floating = of("floating");
  const orphan = of("orphan");

  // Trunk shards: Start pinned top of column 0, scenes wrap every NODES_PER_COLUMN.
  place(START_ID, CENTER_X, TOP_Y, undefined, true);
  const trunkStartY = TOP_Y + ROW_H;
  const { lastCol, maxY: trunkMaxY } = placeTrunkSharded(trunk, CENTER_X, trunkStartY, place);
  const endX = CENTER_X + lastCol * SHARD_COL_W;
  const endY = trunk.length === 0 ? TOP_Y + ROW_H : trunkMaxY + ROW_H;
  place(END_ID, endX, endY, undefined, true);

  const trunkRight = CENTER_X + lastCol * SHARD_COL_W + NODE_W;
  const unanchoredX = Math.max(CENTER_X + COL_GAP, trunkRight + 32);

  // Unanchored chains — right column (shifted right if trunk shards overlap).
  let uy = TOP_Y + ROW_H;
  for (const s of unanchored) {
    place(s.id, unanchoredX, uy, s);
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

  const maxX = Math.max(...nodes.map((n) => n.x + NODE_W));
  const maxY = Math.max(...nodes.map((n) => n.y + NODE_H), bottomY + NODE_H);
  void centerOf; // centers computed in the renderer where node sizes are known
  return { nodes, edges, width: maxX + 80, height: maxY + 80 };
}
