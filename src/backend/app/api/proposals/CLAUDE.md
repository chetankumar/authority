# api/proposals

Accept/reject AI-suggested changes. `ProposalService` is the **only** code path that mutates on behalf of AI output, and both endpoints are author-triggered — this is how the prose hard rule is enforced structurally, not by prompt. Spec: [doc 04 §10](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 05](../../../../../docs/claude-tech-specs/05-ai-system.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| POST | `/api/books/{b}/proposals/{id}/accept` | Locate via conversation index (404 unknown; 409 `already-resolved` if not pending). Apply by type (below). Stamp `applied`/`not-found` + resolvedAt; emit `scene-updated`/`todos-created`. Returns `{ proposal, result }` |
| POST | `/api/books/{b}/proposals/{id}/reject` | Marks `rejected` + resolvedAt; touches nothing else. Returns the Proposal |

## Apply by type

- **edit** — read the target scene's `.md`; find the *first exact occurrence* of `payload.find` (byte-exact, no normalization). Absent → status `not-found`, nothing changes. Present → replace **one** occurrence, save through the standard content path (hash recompute → dependency fanout → settle timer). The sole AI-into-prose path, author-triggered.
- **metadata-update** — apply `newValue` to `field` via SceneService PATCH logic (full validation; XOR rules; failure → 422, proposal stays pending).
- **todo-create** — create the Todo, origin `ai`.

## Accept-all

Client loops accept sequentially, halting to surface any `not-found`. Deliberately no batch endpoint (no batch atomicity).
