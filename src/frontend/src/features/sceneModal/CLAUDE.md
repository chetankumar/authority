# features/sceneModal — Scene Modal (component, not a route)

Everything *about* a scene that isn't its prose. Opened from graph single-click, table ✎, editor's [Metadata], and create flows. 720px, tabs: **Basics · Characters · Summary · Dependencies** (create mode shows Basics only; other tabs appear after first save). Parent: [features](../CLAUDE.md). Spec: [doc 06 §8](../../../../../docs/claude-tech-specs/06-frontend-pages.md).

## Basics

Left — Title*, Description* (textarea), Location, Date/Time, Mood, Emotional Arc. Right — **Sequence** (Previous/Next SearchableSelects, sentinels pinned; splice hint), **Soft placement** (type + scene + ✕ rows; [+ Add placement]), **Structure** (Chapter/Part selects — selecting one clears/disables the other). Footer: [Archive scene] (ghost, left) · [Cancel] [Save scene].
- Save — create `POST /scenes`; edit `PATCH /scenes/{id}`; soft-placement rows diff → `POST/DELETE /relationships`.
- Prev/Next → splice semantics server-side; `affectedScenes` patch the graph.
- Archive → `PATCH {status:"archived"}` (reversible, no confirm) + inline note about chain healing.

## Characters

Chip row (✕ removes) + SearchableSelect "Add character…" → `PATCH {characterIds}`. **↻ AI-redo** → `POST /scenes/{id}/enrich {scope:"characters"}` → spinner; `scene-updated` patches chips live; `result.unrecognizedNames` → amber "Unrecognized: {name} — [Add to characters]".

## Summary

Textarea + [Save summary] (`PATCH {summary}`) · ↻ AI-redo (`enrich {scope:"summary"}`) · hint reflecting the book toggle ("Auto-update on save is **on** — manual edits may be overwritten" / "…**off** — this summary is yours").

## Dependencies

Top "This scene depends on": rows *{title} — {reason}* with ✎ (`PATCH /dependencies/{id}`) and ✕ (`DELETE`). Add row: SearchableSelect (by Seq, self+sentinels excluded) + Reason* + [Add dependency] (`POST /dependencies`; Reason required). Bottom read-only "**Depended on by**" (`GET .../dependencies` dependedOnBy), amber-tinted — the warning before rewriting a scene others lean on.
