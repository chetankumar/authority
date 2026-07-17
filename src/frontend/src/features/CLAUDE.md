# features — per-page folders

Each folder is one page or major modal: its components, local state, and the API calls it makes (via [queries](../queries/CLAUDE.md)/[api](../api/CLAUDE.md)). Shared primitives live in [components](../components/CLAUDE.md).

Parent: [src](../CLAUDE.md). Spec: [doc 06](../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Global shell (in App.tsx, doc 06 §3)

Top bar (48px): logo + "Authority" → `/`; book-title breadcrumb → `/book/{id}`; **git badge** (only when dirty, amber, → `/book/{id}/git`, fed by `git-status` SSE); "Welcome, {name}". Left nav (208px ↔ 56px rail, auto-rails on the editor): outside a book → Home · Settings; inside a book → Scene Graph · Scene Table · Character Sheet · Metadata · Tasks · Resources · Git. Disconnected banner when `/health` polling fails.

## Feature catalog + routes

| Folder | Route | Doc 06 |
|---|---|---|
| [`bookshelf/`](bookshelf/CLAUDE.md) | `/` | §4 |
| [`settings/`](settings/CLAUDE.md) | `/settings/*` | §5 |
| [`graph/`](graph/CLAUDE.md) | `/book/{id}` | §6 |
| [`table/`](table/CLAUDE.md) | `/book/{id}/table` | §7 |
| [`sceneModal/`](sceneModal/CLAUDE.md) | component (not a route) | §8 |
| [`editor/`](editor/CLAUDE.md) | `/book/{id}/scene/{sid}` | §9 |
| [`conversation/`](conversation/CLAUDE.md) | component (not a route) | §10 |
| [`characters/`](characters/CLAUDE.md) | `/book/{id}/characters` | §11 |
| [`metadata/`](metadata/CLAUDE.md) | `/book/{id}/metadata` | §12 |
| [`tasks/`](tasks/CLAUDE.md) | `/book/{id}/tasks` | §13 |
| [`git/`](git/CLAUDE.md) | `/book/{id}/git` | §14 |
| [`resources/`](resources/CLAUDE.md) | `/book/{id}/resources` | §15 |
