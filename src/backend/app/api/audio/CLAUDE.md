# api/audio — scene audio drama

Parent: [api](../CLAUDE.md). Spec: [doc 04 §16](../../../../../docs/claude-tech-specs/04-api-reference.md), [`audio-system.md`](../../../../../docs/audio-system.md).

Mounted at `/api/books/{book_id}/scenes/{scene_id}/audio`. Delegates to `AudioService` / `AudioWorker`. Book-level `GET/PUT /books/{id}/gitignore` lives on the books router.

| Method | Path | Notes |
|---|---|---|
| GET | `/` | Manifest or 404 |
| PATCH | `/lines/{itemId}` | Edit text / voice_settings |
| POST | `/lines/{itemId}/generate` | Enqueue one line |
| POST | `/generate` | Enqueue all `new`/`regenerate` |
| GET | `/lines/{filename}` | `FileResponse` `audio/mpeg` |
| GET | `/stitched` | Optional stitched export |
| DELETE | `/` | Move `audio/` to `.trash/` |
