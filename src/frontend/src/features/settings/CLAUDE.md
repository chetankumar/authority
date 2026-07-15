# features/settings — `/settings/*`

Three pages sharing a 640px centered column; forms label-over-field; Save is the single primary button, disabled until dirty. Parent: [features](../CLAUDE.md). Spec: [doc 06 §5](../../../../../docs/claude-tech-specs/06-frontend-pages.md).

## User Settings

- Author name → `PATCH /settings/user {name}`.
- Books Home path (hint "Folder that will contain all your books") → `PATCH {booksHome}`; 422 path-missing → inline error + [Create this folder] (`createBooksHome:true`); 403 → "Not writable — pick another location".

## AI Settings

- Models table (plain, not AG Grid): Label · Provider · Model name · Key (masked) · Base URL · actions.
- **Model modal:** Provider select drives contextual fields — cloud → Key required; openai-compatible/ollama → Base URL required + example placeholders. Key hint "Paste a key or use ${ENV_VAR}"; edit modal leaves key blank = keep stored. `POST/PATCH /settings/models`; delete → confirm → 409 → BlockedDeletionDialog (AI-Jobs / utility-model refs).
- **Default utility model** select below table → `PATCH /settings/ai`.

## AI-Jobs

Jobs table: Name · Default model · Output type · actions. Modal:
- Name input.
- **Prompt textarea with @-autocomplete** fed by `GET /settings/placeholders` (name + description, filters as typed, Enter/Tab inserts).
- **Output type** select with per-option captions (chat / edit-proposals / metadata-proposals).
- Default model select · [Save job] → `POST/PATCH /settings/ai-jobs`; 422 unknown-placeholder → inline warning + [Save anyway] (`force:true`).
