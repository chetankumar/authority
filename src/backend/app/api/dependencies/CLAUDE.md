# api/dependencies

Dependencies — "Scene 10 depends on Scene 2 because {reason}". When the depended-on scene's content hash changes, a todo is auto-created on each dependent scene. Handled by `SceneService` (fanout on content save). Spec: [doc 04 §6](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 03](../../../../../docs/claude-tech-specs/03-data-storage.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| POST | `/api/books/{b}/dependencies` | `{ sceneId (dependent), dependsOnSceneId (required), reason (required) }`. 422 self-dependency / unknown / archived / sentinel / empty reason / duplicate pair. Creating fires **no** todo |
| PATCH | `/api/books/{b}/dependencies/{id}` | `{ reason }` only (re-pointing = delete + create) |
| DELETE | `/api/books/{b}/dependencies/{id}` | Removes it; existing dependency-generated todos remain (author's to close); no gate |

## Fanout behavior (on content save, see [scenes](../scenes/CLAUDE.md))

When `dependsOnSceneId` content hash changes: create a Todo on each dependent scene — action `"'{depended-on title}' changed — verify dependency: {reason}"`, origin `dependency`, `sourceDependencyId` set. **Dedup:** skip if an *open* todo for the same dependency already exists (typing sessions must not stack duplicates). Emits `todos-created` SSE.
