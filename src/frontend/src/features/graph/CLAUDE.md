# features/graph — `/book/{id}` (Scene Graph)

The book's home: see the story's shape. Full-bleed D3 canvas; floating controls only. Parent: [features](../CLAUDE.md). Spec: [doc 06 §6](../../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Layout

Vertical trunk top-center flowing down (Start pinned top-center; The End anchors trunk bottom). Solid arrows (`--accent`) = hard chain; dotted `--ink-faint` satellites left/right = soft relationships; orphans row along the bottom. Node = 168px surface card, title only (1 line, ellipsis); hover 600ms → description tooltip. Layout is a **pure deterministic function** of `GET /scenes` — same data, same picture; nothing persisted.

## Controls

- Node **single-click** → Scene Modal (edit). **double-click** → `/book/{id}/scene/{sid}` (editor).
- Sentinel pills — non-interactive.
- Canvas drag/wheel/pinch → pan/zoom (D3 zoom; no node dragging).
- **＋ Add scene** (primary, floating) → Scene Modal (create) → `POST /scenes` → node appears via cache patch (200ms fade-in).
- ⤢ Fit to view; edge hover tooltip "definitely after {title}".

Archived scenes are not rendered (the table's Archived filter is their home).

## APIs

`GET /books/{b}/scenes` (scenes + relationships + sentinels). See [SceneModal](../sceneModal/CLAUDE.md) for create/edit.
