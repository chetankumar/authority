# api/jobs

Read access to the job queue — powers the AI Jobs accordion (live transitions ride the book SSE channel; this endpoint is the load/reload read). Handled by `JobService`. Spec: [doc 04 §11](../../../../../docs/claude-tech-specs/04-api-reference.md), [doc 05 worker](../../../../../docs/claude-tech-specs/05-ai-system.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/books/{b}/jobs?scene={id}&status={jobStatus}&type={jobType}` | `[Job]` newest first, filters optional |

## Job model

`{ id, type: user\|system, aiJobId, conversationId, sceneId, scope, modelId, status: queued\|running\|done\|failed, error, result:{unrecognizedNames}, createdAt, startedAt, finishedAt }`. User jobs = AI-Job runs; system jobs = enrichment. Executed by the single asyncio [worker](../../worker/CLAUDE.md) (per-book FIFO, concurrency 1/book, ≤2 global; no auto-retry on failure).
