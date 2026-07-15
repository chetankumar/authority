# api/settings

App-level settings: author identity, model configs, the utility model, AI-Job definitions, and the placeholder registry. All backed by `app.json` (in `appDataRoot`). Handled by `SettingsService` (+ `PlaceholderRegistry`, `ModelFactory` for reference checks). Spec: [doc 04 §3](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 05](../../../../../docs/claude-tech-specs/05-ai-system.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/settings/user` | `{ name, booksHome }` (either may be null pre-setup) |
| PATCH | `/api/settings/user` | `{ name?, booksHome?, createBooksHome? }`. Normalizes/expands path; 422 `path-not-found` unless `createBooksHome`; must be a writable directory (403 via tempfile probe). Invalidates BookScanner cache |
| GET | `/api/settings/models` | `[ModelConfig]` (keys masked) |
| POST | `/api/settings/models` | Provider rules: openai-compatible/ollama require baseUrl. apiKey optional for all providers — empty falls back to the provider default env var (anthropic→`ANTHROPIC_API_KEY`, openai→`OPENAI_API_KEY`, gemini→`GOOGLE_API_KEY`). No connectivity test at save |
| PATCH | `/api/settings/models/{id}` | Omitted `apiKey` keeps stored secret. Re-validates provider rules on merge |
| DELETE | `/api/settings/models/{id}` | 409 `{blockedBy:{aiJobs, utilityModel}}` if referenced |
| POST | `/api/settings/models/{id}/test` | Live check: ModelFactory builds the model (resolving `${ENV_VAR}` now) and sends one `"hello model"` completion (~30s timeout). Returns 200 `ModelTestResult {ok, message?, error?, latencyMs?}` — failures are results, not errors. 404 unknown id. Only settings endpoint doing network I/O; never mutates app.json |
| GET / PATCH | `/api/settings/ai` | `{ utilityModelId }` — model for enrichment + commit-message suggestion. 422 if unknown |
| GET | `/api/settings/ai-jobs` | `[AIJobDefinition]` |
| POST | `/api/settings/ai-jobs` | Validates name/model/outputType; scans prompt tokens `@[a-z0-9_]+` → 422 `{unknownPlaceholders}` unless `force:true` |
| PATCH / DELETE | `/api/settings/ai-jobs/{id}` | Same validation; delete keeps historical name snapshots, no gate |
| GET | `/api/settings/placeholders` | `[Placeholder]` — full registry; single source for the frontend `@` autocomplete |

## Notes

- API keys stored verbatim (literal, `${ENV_VAR}`, or empty = provider default env var), resolved at call time by ModelFactory; **never** leave the server unmasked; **never** stored inside a book folder.
- The model-test endpoint is the one place a key is resolved and used at the app-settings layer; it runs read-only (no lock, no write) and reports connection/auth problems as `ModelTestResult.error` strings.
- `outputType` ∈ `chat | edit-proposals | metadata-proposals` (drives server-side parsing).
