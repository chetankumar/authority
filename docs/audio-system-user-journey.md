# Scene Audio Drama — User Journey

A step-by-step guide to every audio feature in Authority. Read this if you want to **use** scene audio. For the technical build spec (APIs, schemas, code map), see [`audio-system.md`](audio-system.md).

---

## What you get

Authority can turn a scene into an **audio drama**:

1. An AI job **directs** the scene into a script (dialogue, narration, sound effects, performance tags).
2. You **review and Accept** that script — nothing is spoken until you say yes.
3. ElevenLabs **speaks** each line into mp3 files stored with the book.
4. You **listen** in the browser: play the whole scene, start from any line, or audition one line.

**Important principles (so nothing surprises you):**

- The AI **never invents voices**. You cast voices on Characters and on the book Narrator.
- The AI **never writes your prose**. Scene `.md` files stay yours; audio lives beside the scene.
- Spoken audio (`.mp3`) is **not** committed to git. The script (`manifest.json`) **is**, so casting and line text travel with the book.

---

## Big picture

```
One-time setup          Per scene
───────────────         ────────────────────────────────────────
ElevenLabs key    →     Tag who appears in the scene
Sync voices       →     Open Audio modal from the Editor
Cast character    →     Generate script (AI job → Conversation)
  voices                Accept the proposal
Cast narrator     →     Generate pending audio (ElevenLabs)
Define AI-Job     →     Listen, tweak lines, regenerate as needed
```

---

## Part A — One-time setup

Do this once per machine (or when you add new characters / change casting).

### A1. Connect ElevenLabs

1. Open **Settings → AI**.
2. Find the **ElevenLabs** section.
3. Optionally paste an API key. If you leave it blank, Authority uses the environment variable `ELEVENLABS_API_KEY` (including a Machine-level Windows variable if the process can see it).
4. Click **Sync voice library**. Wait until it finishes.
5. Note the “last synced” time — voice pickers use this **cached** list (they do not hit ElevenLabs on every open).

Without a key (UI or env), generation will fail with a clear “no key” error.

### A2. Create an audio-script AI-Job

1. Open **Settings → AI-Jobs**.
2. Create or edit a job.
3. Set **Output type** to **Audio script** (not Chat / Edit / Metadata).
4. Paste a directing prompt. A ready-made one lives at [`audio-system/ai-job-prompt.md`](audio-system/ai-job-prompt.md) — paste everything below its horizontal rule.
5. The prompt must include these placeholders (bare `@` tokens, not wrapped in extra braces):
   - `@current_scene` — the scene’s prose
   - `@scene_speakers` — who is cast for this scene (ids + names only; no voice ids)
   - `@existing_audio_script` — the current manifest, or “(none — first generation)”
6. Save the job. Pick a model you trust for long structured JSON.

You can have one job or several; the Audio modal uses the first job it finds with output type **audio-script**.

### A3. Cast character voices

1. Open the book’s **Characters** page.
2. Expand a character.
3. In **Voice**, open the searchable list of synced ElevenLabs voices.
4. Optionally click the voice preview to hear ElevenLabs’ sample.
5. Optionally click **Suggest voice** — AI proposes a voice from the library using the character sheet (and any unsaved form fields you can see). Suggest does **not** save; you still click **Save**.
6. **Save** the character so `voiceId` / `voiceName` stick.

Repeat for every character who will speak in audio scenes.

### A4. Cast the Narrator

1. Open **Metadata → Book**.
2. Set **Narrator voice** the same way (searchable list from the synced library).
3. Save.

Narration lines use this voice. If it is missing, Accepting an audio script that needs the narrator will fail with a clear error naming Narrator.

### A5. Confirm git ignore for mp3s

Still on **Metadata → Book**, check **Git ignore**:

- New books already include `*.tmp` and `*.mp3`.
- Existing books get `*.mp3` appended the first time audio touches the book.
- You can edit the pattern list; Authority always re-adds `*.tmp` and `*.mp3` if you remove them by mistake.

**Result:** `manifest.json` can be committed; line mp3s stay local regenerable artifacts.

---

## Part B — Per-scene workflow (happy path)

### B1. Tag who is in the scene

1. Open the scene in the Editor (or open **Scene Modal → Characters**).
2. Tag the characters who appear / speak in this scene (involvement as you already do for the book).
3. The audio job’s `@scene_speakers` list is built from these tags **plus** the narrator. Untagged characters are not offered as speakers to the model.

### B2. Open the Audio modal

1. In the Editor toolbar, click **Audio**.
2. A wide modal opens for **this scene only**.

If there is no script yet, you will see an empty state inviting you to **Generate script**.

### B3. Generate the script (AI — no ElevenLabs spend yet)

1. Click **Generate script**.
2. Authority runs your **audio-script** AI-Job for this scene.
3. The **Conversation** modal opens with the job thread.
4. The model should:
   - Analyze tone / subtext (director’s notes in the reply).
   - If a script already exists, reconcile **unchanged / regenerate / new / removed** (UPDATE MODE).
   - Emit one **audio-script** proposal — a full structured script.
5. Review the proposal card (line table + status badges).
6. Click **Accept** (or Accept all).

**What Accept does:**

- Writes / merges `scenes/{sceneId}/audio/manifest.json`.
- Overwrites speaker casting from **your** Character Sheet + Narrator (ignores any voice ids the model invented).
- Keeps byte-identical lines marked `unchanged` (including existing mp3 links).
- Marks changed lines `regenerate` and new lines `new`.
- Drops removed lines and trashes orphan mp3s.
- **Does not** call ElevenLabs.

**If Accept fails with 422:** a speaker used in the script has no voice. Set Narrator and/or that character’s voice, then Accept again.

### B4. Generate spoken audio (ElevenLabs)

Back in the **Audio** modal:

1. Lines that need sound show status **new** or **regenerate** (amber-ish “pending”).
2. Click **Generate all pending (N)** — the button shows how many are queued and is **disabled when N is 0**.
3. Status becomes `running`; the UI refreshes as lines finish (live progress via book events).
4. When done, status is `done` (or `failed` with an error message if something broke).

**Per-line alternative:** click **Regenerate** on a single row. That synthesizes **that line immediately** (it does not only queue it).

### B5. Listen

| Control | What it does |
|---|---|
| **Play scene** (header) | Plays every line that has audio, in order, with short gaps between lines (longer when the speaker changes or an sfx plays). |
| **Stop** | Stops the playlist. |
| **Play** (on a row) | Plays only that line. |
| **From here** (on a row) | Starts the scene playlist at that line and continues to the end. |

While a playlist (or single line) is playing:

- The active row is **highlighted**.
- The list **auto-scrolls** so the current line stays in view.

Playback uses the browser and ordinary mp3 URLs from the API (with cache-busting after regenerate so you hear the new take, not a cached old file).

---

## Part C — Audio modal features in detail

### Header actions

| Button | Behavior |
|---|---|
| **Generate script** | Starts the audio-script AI-Job → opens Conversation. Requires a job with output type audio-script. |
| **Generate all pending (N)** | Synthesizes every line with status `new` or `regenerate`. Disabled when nothing is pending, or while generation is already running. |
| **Play scene** / **Stop** | Full-scene playlist control. |
| **Delete audio** | Asks for confirmation, then moves the whole `scenes/{id}/audio/` folder into the book’s `.trash/`. Script and mp3s can be regenerated later. |

### Each row

| Piece | Behavior |
|---|---|
| Speaker name | From casting (character or narrator); sfx rows show as sfx. |
| Type badge | `dialogue` / `narration` / `sfx`. |
| Status badge | `new` · `regenerate` · `unchanged` (see below). |
| Text area | Edit the spoken text (including ElevenLabs v3 tags the director put in). Blur/save patches the line and marks it **regenerate** if the text changed. |
| Stability slider | For dialogue/narration: tweak ElevenLabs stability; releasing the slider saves and marks **regenerate** if it changed. |
| **Play** | One line. Disabled if there is no mp3 yet. |
| **From here** | Playlist from this line onward. Disabled if there is no mp3 yet. |
| **Regenerate** | Call ElevenLabs for this line now. |
| “No audio yet” | Shown when `renderedFile` is missing. |

Hint under the title chips: *Edit a line or change stability to queue it; Regenerate on a row runs that line now.*

### Line statuses (“pending” explained)

| Status | Meaning | In “Generate all pending”? |
|---|---|---|
| **new** | Never synthesized, or newly added by Accept. | Yes |
| **regenerate** | Needs a new take (edited text/settings, or marked by UPDATE MODE Accept). Old mp3 may still play until you generate. | Yes |
| **unchanged** | Script and audio are considered in sync. | No |

**How a line becomes pending without clicking Regenerate:**

- Edit the row text and leave the field (save).
- Change stability and release the slider.
- Accept an updated audio-script proposal that classifies the line as `new` or `regenerate`.

**How a line leaves pending:**

- Successful synthesis sets it to `unchanged` and points `renderedFile` at the mp3.

### After you change the prose of the scene

1. Edit and save the scene markdown as usual.
2. Open Audio → **Generate script** again.
3. In Conversation, review UPDATE MODE: which lines stay, which regenerate, which are new/removed.
4. **Accept**.
5. **Generate all pending** — only the lines that need new audio cost ElevenLabs credits. Unchanged lines keep their existing files.

---

## Part D — What lives on disk (plain language)

For each scene that has audio:

```
scenes/{sceneId}/audio/
  manifest.json          ← script + status + links to files (git-tracked)
  lines/
    001-chr-….mp3        ← one file per sequence line (gitignored)
    002-narrator-….mp3
    …
  scene_stitched.mp3     ← optional combined file after a batch generate
```

- **Play scene** does **not** require the stitched file; it plays the line files in order.
- Filenames are stable (`position-speaker-id`). Regenerating overwrites the same path; the UI appends a version query so the browser fetches the new bytes.
- Deleting audio from the modal moves the whole folder to `.trash/` (recoverable from trash on disk if you need to dig).

---

## Part E — Casting & Accept rules (why things fail)

| Situation | What happens |
|---|---|
| Character tagged in scene but no voice on the Character sheet | Accept fails naming that character. |
| Narrator voice unset on Metadata → Book | Accept fails naming Narrator. |
| Model invents a `voice_id` in JSON | Ignored; server overwrites from your casting. |
| Model invents a speaker id not in `@scene_speakers` | Should not happen with a good prompt; Accept validation expects known speakers for non-sfx lines. |
| ElevenLabs key missing | Generate fails with no-key. |
| Generation already running | New generate returns conflict; wait or watch status. |
| Empty / invalid spoken text after tags stripped | ElevenLabs may 400; fix the line text and Regenerate. |

---

## Part F — Settings & surfaces checklist

| Where | What you use it for |
|---|---|
| **Settings → AI** | ElevenLabs key (optional) + **Sync voice library** |
| **Settings → AI-Jobs** | Define the **audio-script** directing job + prompt |
| **Characters** | Per-character voice, preview, Suggest voice, Save |
| **Metadata → Book** | Narrator voice + Git ignore patterns |
| **Scene Modal → Characters** | Tag who appears in this scene |
| **Editor → Audio** | Script, synthesize, listen, edit, delete |
| **Conversation Modal** | Review / Accept the audio-script proposal |

---

## Part G — Typical day-to-day recipes

### First time on a scene

1. Voices cast (characters + narrator), AI-Job ready, voices synced.
2. Tag scene characters.
3. Audio → Generate script → Accept.
4. Generate all pending.
5. Play scene; tweak any bad lines → Regenerate those rows.

### Fix one awkward line

1. Edit the text (or stability) in the Audio modal.
2. Either wait and use **Generate all pending**, or click **Regenerate** on that row.
3. Play the row to confirm (you should hear the new take).

### After a chapter rewrite

1. Generate script again → read the reconciliation in Conversation.
2. Accept.
3. Generate all pending only.

### Throw it all away for this scene

1. Audio → **Delete audio** → confirm.
2. Start again from Generate script.

---

## Part H — What the AI is (and is not) doing

**Is doing:** directing performance (tags, stability, which lines change), structuring dialogue / narration / sfx, reconciling against an existing script so you do not re-pay for unchanged lines.

**Is not doing:** inventing ElevenLabs voice ids, writing scene prose, synthesizing audio on Accept, committing mp3s to git.

Paste / refine the directing prompt from [`audio-system/ai-job-prompt.md`](audio-system/ai-job-prompt.md). The build-oriented behavior map stays in [`audio-system.md`](audio-system.md).

---

## Quick reference — buttons you will click most

1. **Sync voice library** (once / when the library changes)
2. **Save** character + narrator voices
3. **Generate script** → **Accept**
4. **Generate all pending**
5. **Play scene** / **From here** / **Play**
6. **Regenerate** on lines you hand-tuned
