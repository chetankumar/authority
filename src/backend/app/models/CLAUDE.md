# models — Pydantic schemas & enums

Every request/response body and every on-disk JSON document corresponds to a Pydantic model. The same models validate the API boundary **and** validate documents at book load (load-time schema validation; violations treated as corruption per doc 03). Treat this as the OpenAPI components section.

Parent: [app](../CLAUDE.md). Specs: [04 API §2](../../../../docs/claude-tech-specs/04-api-reference.md) (shared objects + enums), [03 Data](../../../../docs/claude-tech-specs/03-data-storage.md) (on-disk schemas).

## Enums (doc 04 §2.1)

`provider` (anthropic · openai · gemini · openai-compatible · ollama) · `outputType` (chat · edit-proposals · metadata-proposals) · `placement` (trunk · unanchored · floating · orphan · archived — **computed**, never stored) · `sceneStatus` (active · archived) · `relationshipType` (before · after · around) · `todoStatus` (open · done · closed) · `todoOrigin` (user · dependency · ai) · `conversationKind` (note · chat · ai-job · task-discussion) · `proposalType` (edit · metadata-update · todo-create) · `proposalStatus` (pending · applied · rejected · not-found) · `jobType` (user · system) · `jobStatus` (queued · running · done · failed) · `jobScope` (full · selection · summary · characters · both) · `parentType` (scene · chapter · part · book) · `gitFileStatus` (modified · added · deleted · untracked · renamed).

## Shared objects (doc 04 §2.2)

`ModelConfig` (responses carry `apiKeyMasked`, never the real key) · `ModelTestResult` (live model check: `ok`, `message?`, `error?`, `latencyMs?`) · `AIJobDefinition` · `Placeholder` · `BookSummary` · `Book` · `Part` · `Chapter` · `Scene` (metadata; `seq`/`placement` computed on read; `chapterId` XOR `partId`) · `SoftRelationship` · `Dependency` · `Character` (+ computed `sceneCount`) · `Plotline` (+ `sceneCount`) · `Todo` (+ resolved `parentTitle`) · `ConversationSummary` · `Conversation` · `Message` · `Proposal` (payload variants: edit / metadata-update / todo-create) · `Job` · `GitFile` · `GitStatus` · `CommitInfo` · `CheckItem` · `CompileReport`.

## ID scheme (doc 03)

`{prefix}-{6 lowercase hex}` via `secrets.token_hex(3)`, collision-checked per collection. Prefixes: `bok scn chp prt chr plt cnv msg tdo dep rel job prp mdl aij`. Sentinels `scn-START` / `scn-END` are reserved, recordless, and valid relationship endpoints.
