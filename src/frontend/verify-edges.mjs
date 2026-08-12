import { computeLayout } from "./src/features/graph/layout.ts";
import { hardChainEdgeD } from "./src/features/graph/edgePaths.ts";
import { START_ID, END_ID } from "./src/api/scenes.ts";

function mockTrunk(n) {
  const base = {
    file: "x.md",
    description: "d",
    location: "",
    dateTime: "",
    chapterId: null,
    partId: null,
    primaryPlotlineId: null,
    secondaryPlotlineIds: [],
    mood: "",
    emotionalArc: "",
    summary: "",
    characters: [],
    status: "active",
    contentHash: "",
    wordCount: 0,
    placement: "trunk",
    createdAt: "",
    updatedAt: "",
  };
  const scenes = [];
  for (let i = 0; i < n; i++) {
    const id = `scn-${String(i).padStart(6, "0")}`;
    const prev = i === 0 ? START_ID : `scn-${String(i - 1).padStart(6, "0")}`;
    const next = i === n - 1 ? END_ID : `scn-${String(i + 1).padStart(6, "0")}`;
    scenes.push({ ...base, id, title: `Scene ${i + 1}`, previousSceneId: prev, nextSceneId: next, seq: i + 1 });
  }
  return scenes;
}

const layout = computeLayout(mockTrunk(25), []);
const node = (title) => layout.nodes.find((n) => n.title === title);
const start = layout.nodes.find((n) => n.id === START_ID);
const end = layout.nodes.find((n) => n.id === END_ID);

const sameCol = hardChainEdgeD(node("Scene 5"), node("Scene 6"));
const wrap = hardChainEdgeD(node("Scene 10"), node("Scene 11"));
const toEnd = hardChainEdgeD(node("Scene 25"), end);

console.log("same-column:", sameCol);
console.log("wrap:", wrap);
console.log("to-end:", toEnd);

const sameColVertical = sameCol.includes("M ") && sameCol.split(" L ").length === 2;
const wrapOrthogonal =
  wrap.includes(" L ") &&
  wrap.split(" L ").length === 4 &&
  !wrap.match(/M [\d.]+ [\d.]+ L [\d.]+ [\d.]+ L [\d.]+ [\d.]+$/);
const endVertical = toEnd.startsWith(`M ${node("Scene 25").x + 84}`) && toEnd.split(" L ").length === 2;

const ok = sameColVertical && wrapOrthogonal && endVertical;
console.log(ok ? "ALL CHECKS PASSED" : "SOME CHECKS FAILED");
process.exit(ok ? 0 : 1);
