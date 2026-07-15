# Authority — Technical Specification

**Version:** 1.0 (for author review, then handoff to Claude Code)
**Date:** 2026-07-15

Authority is a local, browser-based, AI-assisted novel-writing studio. This documentation set is the complete build specification. It supersedes the earlier requirements draft; every decision made during journey-based planning is captured here.

## Document map

| Doc | Contents |
|---|---|
| `01-overview-and-principles.md` | Vision, hard rules, the write-permission model, tech stack summary |
| `02-architecture-and-launcher.md` | Process model, launcher scripts, ports, logging, repo layout |
| `03-data-storage.md` | Every JSON file and schema, ID scheme, atomic-write semantics, scene files |
| `04-api-reference.md` | Every endpoint: purpose, request, response, behavior, errors |
| `05-ai-system.md` | LangChain integration, models, placeholders, AI-Jobs, enrichment, proposals, job worker, SSE |
| `06-frontend-pages.md` | Every page and modal: layout, contents, button behavior, which APIs each control calls |
| `07-decisions-and-deferred.md` | Closed decisions (with defaults the author may veto), deferred features, glossary |

## Reading order for implementation

Claude Code should read 01 → 02 → 03 → 05 → 04 → 06, then build in the phase order given at the end of `02-architecture-and-launcher.md`.

## Non-negotiable rules (repeated everywhere they matter)

1. **The AI never writes, edits, or touches scene prose (.md files).** It may only emit find/replace edit *proposals*; text changes only when the author applies them.
2. **JSON files are the only persistence.** No SQLite, no Redis, no external DB. All writes are atomic (temp file + rename). The API server is the single writer.
3. **Each book is a self-contained, portable folder and a git repository.** No book data is ever stored at app level.
4. **Local, single-user, no auth.** The API binds to localhost.
