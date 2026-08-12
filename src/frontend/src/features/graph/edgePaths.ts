import { NODE_H, NODE_W, type LayoutNode } from "./layout";

/** Hard-chain edge: straight vertical within a column, gutter-routed orthogonal path on shard wrap. */
export function hardChainEdgeD(from: LayoutNode, to: LayoutNode): string {
  const cx = from.x + NODE_W / 2;
  const exitY = from.y + NODE_H;
  const entryX = to.x + NODE_W / 2;
  const entryY = to.y;

  const isWrap = from.x < to.x && to.y < from.y + NODE_H;
  if (isWrap) {
    const fromY = from.y + NODE_H / 2;
    const toY = to.y + NODE_H / 2;
    const columnGap = to.x - from.x - NODE_W;
    const gutterX = from.x + NODE_W + columnGap / 2;
    const exitX = from.x + NODE_W;

    return `M ${exitX} ${fromY} L ${gutterX} ${fromY} L ${gutterX} ${toY} L ${to.x} ${toY}`;
  }

  return `M ${cx} ${exitY} L ${entryX} ${entryY}`;
}
