# api/structure — parts & chapters

Structural containers: parts and chapters, both ordered by simple `seq` integer. A chapter belongs to a part; a scene belongs to a chapter XOR directly to a part. Handled by `StructureService`. Spec: [doc 04 §7](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 03](../../../../../docs/claude-tech-specs/03-data-storage.md).

## Parts

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/parts` | `[Part]` sorted by seq |
| POST | `/api/books/{b}/parts` | `{ title (req), description? }`. Assigns seq = max + 1. 201 Part |
| PATCH | `/api/books/{b}/parts/{id}` | `{ title?, description? }` — metadata only. Returns Part |
| POST | `/api/books/{b}/parts/reorder` | `{ ids: [...] }` — reassigns seq 1..n in given order. Returns `[Part]` |
| DELETE | `/api/books/{b}/parts/{id}` | 409 `{blockedBy:{chapters, scenes}}` if referenced. Else delete + compact seq. 204 |

## Chapters

Same CRUD contract as parts, plus:
- GET → `[Chapter]` each carrying `partId`, sorted by global seq (client groups by part; part-less → "Unassigned").
- POST accepts `partId?` (assignable later; **required for compilation**). Auto-assigns next seq.
- PATCH accepts `partId` (or `null` to unassign). Metadata only, no reordering.
- POST `/api/books/{b}/chapters/reorder` — same semantics as parts reorder.
- DELETE 409 while any scene has this `chapterId`, listing them. Compacts seq on success.

## Persistence

Parts and chapters live in `db/parts.json` and `db/chapters.json` as arrays with `seq` integer ordering.
