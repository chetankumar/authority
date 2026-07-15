# api/structure — parts & chapters

Structural containers: parts and chapters, both ordered linked lists. A chapter belongs to a part; a scene belongs to a chapter XOR directly to a part. Handled by `StructureService` (+ `ChainService` for ordering). This maps to the single "structure" router in doc 02. Spec: [doc 04 §7](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 03](../../../../../docs/claude-tech-specs/03-data-storage.md).

## Parts

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/parts` | `[Part]` chain-ordered; broken links repaired best-effort at load |
| POST | `/api/books/{b}/parts` | `{ title (req), description? }`. Appends to chain tail. 201 Part |
| PATCH | `/api/books/{b}/parts/{id}` | `{ title?, description?, moveBefore?, moveAfter? }` (mutually exclusive → 422). Returns the full ordered `[Part]` |
| DELETE | `/api/books/{b}/parts/{id}` | 409 `{blockedBy:{chapters, scenes}}` if referenced — author must unassign first (strict; nothing auto-unassigned). Else heal chain + delete. 204 |

## Chapters

Same contract as parts, plus:
- GET → `[Chapter]` each carrying `partId`, chain-ordered (client groups by part; part-less → "Unassigned").
- POST accepts `partId?` (assignable later; **required for compilation**).
- PATCH accepts `partId` (or `null` to unassign).
- DELETE 409 while any scene has this `chapterId`, listing them.

## Persistence

Parts and chapters live in `config/book.json` as linked lists (prev/next); the API always returns them pre-ordered.
