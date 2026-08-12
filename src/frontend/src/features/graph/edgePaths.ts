import { NODE_H, NODE_W, ROW_H, type LayoutNode } from "./layout";

/** Hard-chain edge: straight vertical within a column, orthogonal Z-path on shard wrap. */
export function hardChainEdgeD(from: LayoutNode, to: LayoutNode): string {
  const cx = from.x + NODE_W / 2;
  const exitY = from.y + NODE_H;
  const entryX = to.x + NODE_W / 2;
  const entryY = to.y;

  const isWrap = from.x < to.x && to.y < from.y + NODE_H;
  if (isWrap) {
    const laneY = exitY + (ROW_H - NODE_H) / 2;
    return `M ${cx} ${exitY} L ${cx} ${laneY} L ${entryX} ${laneY} L ${entryX} ${entryY}`;
  }

  return `M ${cx} ${exitY} L ${entryX} ${entryY}`;
}
