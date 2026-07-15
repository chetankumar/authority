# features/settings — `/settings/*`

Three pages sharing a 640px centered column; forms label-over-field; Save is the single primary button, disabled until dirty. Parent: [features](../CLAUDE.md). Spec: [doc 06 §5](../../../../../docs/claude-tech-specs/06-frontend-pages.md).

## User Settings

- Author name → `PATCH /settings/user {name}`.
- Books Home path (hint "Folder that will contain all your books") → `PATCH {booksHome}`; 422 path-missing → inline error + [Create this folder] (`createBooksHome:true`); 403 → "Not writable — pick another location".

## AI Settings

- Models table (plain, not AG Grid): Label · Provider · Model name · Key (masked) · Base URL · actions.
- **Model modal:** Provider select drives contextual fields — openai-compatible/ollama → Base URL required + example placeholders. Key is optional: blank uses the provider's default env var (anthropic→`ANTHROPIC_API_KEY`, openai→`OPENAI_API_KEY`, gemini→`GOOGLE_API_KEY`); a literal or `${ENV_VAR}` also work. Edit modal leaves key blank = keep stored. `POST/PATCH /settings/models`; delete → confirm → 409 → BlockedDeletionDialog (AI-Jobs / utility-model refs).
- **Test row action** (↯): `POST /settings/models/{id}/test` runs a live `hello model` completion. Spinner while in flight; result renders as a chip (green "OK · {ms}ms" / red "Failed", reason on hover) plus a toast. Failures arrive as 200 `ModelTestResult` bodies, not thrown errors.
- **Default utility model** select below table → `PATCH /settings/ai`.

## AI-Jobs

Jobs table: Name · Default model · Output type · actions. Modal:
- Name input.
- **Prompt textarea with @-autocomplete** fed by `GET /settings/placeholders` (name + description, filters as typed, Enter/Tab inserts).
- **Output type** select with per-option captions (chat / edit-proposals / metadata-proposals).
- Default model select · [Save job] → `POST/PATCH /settings/ai-jobs`; 422 unknown-placeholder → inline warning + [Save anyway] (`force:true`).
