# api/health

Launcher readiness poll and frontend disconnect detection. Spec: [doc 04 §3](../../../../../docs/claude-tech-specs/04-api-reference.md).

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/api/health` | Response `{ "status": "ok", "version": "1.0.0" }`. No services engaged. |

## Consumers

- Launcher polls this until 200 before opening the browser (timeout ~60s).
- Frontend polls it to drive the "Backend not responding" disconnected banner ([global shell](../../../../frontend/src/features/CLAUDE.md)).
