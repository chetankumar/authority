# features/audio — Editor Audio Modal

Parent: [features](../CLAUDE.md). Spec: [doc 06](../../../../docs/claude-tech-specs/06-frontend-pages.md) (Audio Modal), [`audio-system.md`](../../../../docs/audio-system.md).

Not a route — opened from the Editor toolbar **Audio** button (`EditorPage`).

| File | Role |
|---|---|
| `AudioModal.tsx` | Generate script (AI-Job → Conversation Modal), edit rows, pending batch generate, per-line regen/play/**From here**, **Play scene** playlist with gaps + active-row highlight/scroll, delete |

API/hooks: `api/audio.ts`, `queries/audio.ts`, `keys.audio` / `keys.gitignore`. SSE `audio-progress` → `useBookEvents` invalidates the scene audio query.
