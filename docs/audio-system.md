# Scene Audio Drama — ElevenLabs TTS Narration (Build Spec)

**Status:** ✅ **implemented** (Phase 12, 2026-07-18). Authoritative product/behavior spec for scene audio. Tech specs 01/03/04/05/06 and [`BUILD-TODO.md`](BUILD-TODO.md) Phase 12 are in sync. Do not invent a parallel persistence or AI stack — extend the paths listed in §0.

**Product decisions (locked):**

- Voices live on the **Character Sheet** / book **Narrator** — never invented by the LLM.
- Script half reuses **AI-Job → conversation → proposal → Accept (merge)**.
- Listen/edit half is a **dedicated Editor Audio Modal** (not a Scene Modal tab).
- Playback is a **browser playlist** over FastAPI `FileResponse` mp3s — no streaming server.
- `*.mp3` is **gitignored** in the book; `manifest.json` is tracked.

Reference pipeline (behavior ported into `AudioService`, not run as a subprocess): [`audio-system/speech_generator.py`](audio-system/speech_generator.py), [`audio-system/json-generator-prompt.md`](audio-system/json-generator-prompt.md), [`audio-system/speech_ref.json`](audio-system/speech_ref.json).

---

## 0. Spec + implementation map

| Doc / file | Why |
|---|---|
| [`../CLAUDE.md`](../CLAUDE.md) | Hard rules |
| [`claude-tech-specs/01-overview-and-principles.md`](claude-tech-specs/01-overview-and-principles.md) | Write-permission model (audio rows) |
| [`claude-tech-specs/03-data-storage.md`](claude-tech-specs/03-data-storage.md) | `scenes/{id}/audio/`, voices, gitignore |
| [`claude-tech-specs/04-api-reference.md`](claude-tech-specs/04-api-reference.md) | §16 Audio + ElevenLabs settings |
| [`claude-tech-specs/05-ai-system.md`](claude-tech-specs/05-ai-system.md) | Placeholders, `audio-script`, proposals |
| [`claude-tech-specs/06-frontend-pages.md`](claude-tech-specs/06-frontend-pages.md) | Editor Audio Modal, Characters, Metadata, Conversation |
| [`BUILD-TODO.md`](BUILD-TODO.md) | Phase 12 checklist (all ✅) |
| `src/backend/app/services/audio_service.py` | Manifest merge, synth, stitch, gitignore |
| `src/backend/app/worker/audio_worker.py` | Batch / single-line queue + `audio-progress` SSE |
| `src/backend/app/api/audio/router.py` | Scene audio HTTP surface |
| `src/backend/app/core/secrets.py` | `resolve_secret(..., default_env="ELEVENLABS_API_KEY")` |
| `src/frontend/src/features/audio/AudioModal.tsx` | Edit / regen / playlist Play scene |

---

## 1. What this feature is

Two halves:

1. **Script generation (AI, free until Accept)** — An `audio-script` AI-Job turns scene prose into a structured manifest (dialogue / narration / sfx lines with v3 tags and voice settings). UPDATE MODE reconciles against `@existing_audio_script`. Accept **merges** into `scenes/{id}/audio/manifest.json` and overwrites `speakers` from Character Sheet / Narrator.
2. **Synthesis + listen (ElevenLabs + browser)** — Editor **Audio Modal** edits the saved script, regenerates per line or in batch, and **Play scene** plays line mp3s in order with gaps (playlist). FastAPI only serves static files.

### 1.1 Voices on Character Sheet, not in the prompt

- Each character: `voiceId` + `voiceName` on `db/characters.json`.
- Narrator: `narratorVoiceId` + `narratorVoiceName` on `config/book.json`.
- `@scene_speakers` gives the model **ids + names only** (no voice ids).
- On Accept, server builds authoritative `speakers` and **never trusts** model `voice_id` / `voice_name`.
- Voice library: cached in `app.json`; picker + preview + optional AI-suggest on Character Sheet.

### 1.2 Hard-rule compliance

- Never write scene `.md`.
- JSON + binary under `scenes/{id}/audio/` (binary precedent: `resources/`, covers).
- Single writer: ElevenLabs only inside FastAPI `AudioService` (no subprocess of `speech_generator.py`).
- Atomic writes via `app/core/atomic.py`.
- Voice library + API key are app-level (`app.json`); mp3s and manifest travel with the book (mp3s gitignored).

---

## 2. User journey

### One-time setup (UI + endpoints)

| Step | UI | Action | Endpoints |
|---|---|---|---|
| 1 | **Settings → AI** | Optional ElevenLabs key (else env `ELEVENLABS_API_KEY`). **Sync voice library**. | `GET/PATCH /api/settings/elevenlabs`, `POST .../voices/sync`, `GET .../voices` |
| 2 | **Settings → AI-Jobs** | Job output type **audio-script**; prompt uses `@current_scene`, `@scene_speakers`, `@existing_audio_script`. | Existing AI-Jobs CRUD |
| 3 | **Characters** | Voice picker + preview + **Suggest voice** per character; Save. | Voices GET; `POST .../characters/{id}/voice/suggest`; `PATCH .../characters/{id}` |
| 4 | **Metadata → Book** | Narrator voice; **Git ignore** (includes `*.mp3`). | `PATCH /books/{b}`; `GET/PUT /books/{b}/gitignore` |

**Key resolution:** `resolve_secret(raw, default_env="ELEVENLABS_API_KEY")` — empty app setting falls back to env.

### Per scene

1. Tag speakers on Scene Modal → Characters.
2. Editor toolbar → **Audio** → Audio Modal.
3. **Generate script** → AI-Job → Conversation Modal → review proposal → **Accept** (merge).
4. **Generate all pending** and/or per-line **Regenerate**.
5. **Play scene** (playlist) or play one line.

After prose edits: re-run job → Accept (merge preserves unchanged `renderedFile`) → generate only pending.

---

## 3. Data model

### 3.1 Character — `voiceId` / `voiceName`

On all of `CharacterRecord`, `Character`, `CharacterCreate`, `CharacterUpdate` (partial PATCH stays `| None`).

### 3.2 Book — narrator voice

On book config / `PATCH /books/{id}`: `narratorVoiceId`, `narratorVoiceName`.

### 3.3 App-level ElevenLabs

`VoiceInfo` + on `AppData`: `elevenLabsApiKey`, `elevenLabsVoices`, `elevenLabsVoicesSyncedAt`. Mask/patch like `ModelConfig.apiKey`. **Not** a `ModelConfig` / LangChain provider.

`${ENV_VAR}` resolution lives in `app/core/secrets.py`; `model_factory` and Audio/Settings call it. ElevenLabs default env: `ELEVENLABS_API_KEY`.

### 3.4 Manifest — `scenes/{id}/audio/manifest.json`

```
scenes/{sceneId}/audio/
  manifest.json
  lines/{position:03d}-{speaker_id}-{item_id}.mp3
  scene_stitched.mp3          # optional batch artifact; Play scene does not require it
```

Each sequence item links audio via **`renderedFile`** (filename under `lines/`). Manifest is the source of truth; no separate index.

Enums: `AudioSequenceItemType`, `AudioLineStatus` (`new`/`regenerate`/`unchanged`), `AudioSynthesisStatus`, plus `OutputType.audio_script`, `ProposalType.audio_script_create`, `AudioScriptCreatePayload`.

Speaker keys: character ids (`chr-…`) + reserved `"narrator"`.

### 3.5 Gitignore

- New books: `.gitignore` seeds `*.tmp` and `*.mp3`.
- Existing: `ensure_gitignore_patterns` appends `*.mp3` if missing.
- Metadata → Book edits patterns via `GET/PUT /books/{b}/gitignore`; save always re-injects `*.tmp` and `*.mp3` if absent.
- Source of truth = book root `.gitignore` file (not duplicated in `book.json`).
- `manifest.json` **is** committed; mp3s are not.

---

## 4. Backend — AI-Job (script half)

### 4.1 Placeholders

| Token | Status today | Resolver |
|---|---|---|
| `@current_scene` | Exists | Scene prose |
| `@scene_speakers` | **Add** | Tagged characters as `speaker_id "chr-…" — Name` + narrator; no voice ids. Empty tags → message that only narrator is available |
| `@existing_audio_script` | **Add** | `json.dumps(manifest)` or `"(none — first generation)"` |

`@scene_characters` is **not** a substitute (full sheets, not casting ids).

### 4.2 Prepare / parse / accept

- `AiJobService.prepare`: append `AUDIO_SCRIPT_FORMAT_INSTRUCTIONS` for `outputType == audio_script`.
- `parse_audio_script` → one `audio-script-create` proposal (whole manifest).
- `ConversationService` dispatches on `outputType` (scene parent only).
- `ProposalService._apply_audio_script_create` → `AudioService.save_manifest` (**merge**, see §5).

Accept never calls ElevenLabs.

---

## 5. Merge on Accept (diff and apply)

1. Validate candidate as `AudioManifest`.
2. Load existing manifest if any.
3. Assemble authoritative `speakers` from Character Sheet + Narrator (overwrite model voices). Keep model `direction` if present.
4. Merge sequence by item `id`:
   - **`unchanged`**: keep **old** item verbatim (text, voice_settings, `renderedFile`). Ignore model echo.
   - **`regenerate`**: take new text/settings; keep old `renderedFile` until synth replaces it; status `regenerate`.
   - **`new`**: insert; `renderedFile=null`.
   - Removed ids: drop from sequence; move orphan mp3s to `.trash/`.
5. Validate every non-sfx `speaker_id` has non-empty `voice_id` — else 422 naming the character.
6. Atomic write; `notify_changed`.

---

## 6. Backend — `AudioService` + `AudioWorker`

### AudioService

Mirror `resource_service.py` path/scan/trash/lock discipline.

- `save_manifest` — §5
- `synthesize_line` — ElevenLabs TTS (`eleven_v3`) / SFX in `asyncio.to_thread`; write via `atomic_write_bytes`; set `renderedFile`
- `stitch` — optional; port gaps from `speech_generator.py`
- `path_for_line` / `path_for_stitched` — 404 if absent
- `update_line` — PATCH text/voice_settings; mark `regenerate` when content changed
- Pure helpers: `audio_dir`, `read_manifest_if_exists`, `safe_audio_filename`, `ensure_gitignore_patterns` (or on BookService)

### AudioWorker

- Queue `(book_id, scene_id)` or single-line jobs; global concurrency 1 for batch jobs.
- Per-line semaphore (2–3) inside a job.
- Emit `audio-progress` SSE: `{ sceneId, phase, lineId?, completed, total, message? }`.
- Fail job if any required line fails; leave those items `new`/`regenerate` for retry.
- Wire in `deps.py` + `main.py` lifespan like `GitStatusWorker`.

---

## 7. API

### Scene audio — `/api/books/{b}/scenes/{s}/audio`

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/` | Manifest or 404 |
| `PATCH` | `/lines/{itemId}` | Edit text / voice_settings |
| `POST` | `/lines/{itemId}/generate` | Synth one line |
| `POST` | `/generate` | Synth all `new`/`regenerate`; 409 if already running |
| `GET` | `/lines/{filename}` | `FileResponse` `audio/mpeg` |
| `GET` | `/stitched` | Optional stitched mp3 |
| `DELETE` | `/` | Move audio folder to `.trash/` |

### Settings

`GET/PATCH /settings/elevenlabs`, `POST /settings/elevenlabs/voices/sync`, `GET /settings/elevenlabs/voices`.

### Characters / books

`POST /characters/{id}/voice/suggest` (writes nothing).  
`GET/PUT /books/{b}/gitignore`.

---

## 8. Frontend

### Surfaces

| Surface | Change |
|---|---|
| Settings → AI | ElevenLabs key + Sync voices |
| Settings → AI-Jobs | `audio-script` output type |
| Characters | Voice `SearchableSelect`, preview, **Suggest voice** |
| Metadata → Book | Narrator voice + Git ignore textarea |
| **Editor** | Toolbar **Audio** opens **Audio Modal** (not Scene Modal) |
| Conversation Modal | `audio-script-create` proposal card (line table + status badges) |
| `useBookEvents` | `audio-progress` → merge into query cache |

### Audio Modal

Header: Generate script | Generate all pending | Play scene | Stop | Delete.  
Body: editable rows (text, stability slider, status, per-line play, Regenerate).  
Play scene: client playlist with `DEFAULT_GAP_MS` / `SPEAKER_CHANGE_GAP_MS` / `SFX_GAP_MS` — no stream API.

Files: `features/audio/AudioModal.tsx`, `api/audio.ts`, `queries/audio.ts`, `keys.audio`.

---

## 9. Dependencies

`elevenlabs`, `pydub` in `requirements.txt`. Non-fatal startup warning if `ffmpeg` missing from PATH.

---

## 10. BUILD-TODO — Phase 12

See [`BUILD-TODO.md`](BUILD-TODO.md) § Phase 12. Also keep docs 01/03/04/05/06 in sync when marking items ✅.

---

## 11. Build order

1. Models + `secrets.py` (`ELEVENLABS_API_KEY` default)
2. Book gitignore defaults + Metadata gitignore UI + ensure-on-open
3. ElevenLabs settings + Character/Book voice UI + suggest
4. Placeholders + AI-Job path + Accept merge
5. AudioService / Worker / APIs
6. Editor Audio Modal + playlist + proposal card + SSE
7. Doc polish / BUILD-TODO status

---

## 12. Verification checklist

1. Env-only key works without UI paste; Sync populates cached voices; GET voices does not hit network.
2. Character voice + Suggest + Narrator round-trip.
3. Gitignore contains `*.mp3`; Metadata editor persists patterns; mp3s never appear as new commits.
4. Audio-script job Accept merges speakers from Character Sheet; unassigned voice → 422, no write.
5. Generate → SSE progress → line mp3s play; Play scene playlist with gaps.
6. UPDATE MODE: unchanged lines keep byte-identical text/`renderedFile`; second generate with no changes → zero ElevenLabs calls.
7. Per-line edit + Regenerate only re-hits that line.
8. No new code path writes scene `.md`.
