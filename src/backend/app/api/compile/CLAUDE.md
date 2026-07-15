# api/compile

Compilation is a **gate**: a completeness check (errors block, warnings inform), then wipe-and-regenerate `compiled-book/`. Also powers the standing readiness indicator on the Metadata page. `CompileService` + `ChainService` + `StructureService`. Spec: [doc 04 §14](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 07](../../../../../docs/claude-tech-specs/07-decisions-and-deferred.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/compile/check` | `{ ready, errors:[CheckItem], warnings:[CheckItem] }`. Pure read; standing indicator |
| POST | `/api/books/{b}/compile` | Re-run check; errors → 409 `{errors}`, nothing written. Else wipe `compiled-book/`, regenerate, emit `compile-done` + `git-status`. Returns CompileReport |

## Check items

**Errors (block):** `scene-no-chapter` · `chain-broken` · `chain-not-single-path` · `chain-cycle` · `scene-floating` · `scene-orphan` · `chapter-no-part` · `chapter-not-contiguous` · `soft-relation-contradicted`.
**Warnings (inform):** `chapter-empty` (emitted heading-only) · `part-empty` · `scene-no-summary` · `soft-relation-redundant`.

Each `CheckItem` carries a stable machine `type` + `subjects` for UI deep-linking.

## Build output

For each part in chain order → `part-{n}-{slug}/`; each chapter in chain order → `chapter-{n}-{slug}.md` = `# {chapter title}\n\n` + scenes' prose in chain order joined by `\n\n***\n\n`. Empty chapters emit heading-only (warning). Output lands **uncommitted** — committing is the author's deliberate act; compile never auto-commits.
