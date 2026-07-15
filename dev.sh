#!/usr/bin/env bash
set -euo pipefail

# Authority — Mac/Linux development mode (doc 02)
# Starts Uvicorn with --reload and Vite dev server in parallel.
# Vite proxies /api to the backend (see vite.config.ts).
# For working on Authority itself, never for writing.

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PORT=8700
ENV_NAME="authority"
BACKEND="$ROOT/src/backend"
FRONTEND="$ROOT/src/frontend"

if curl -s -o /dev/null -w '%{http_code}' "http://localhost:$PORT/api/health" 2>/dev/null | grep -q 200; then
    echo "[Authority DEV] Backend already running on port $PORT. Stop it first."
    exit 1
fi

USE_CONDA=0
if command -v conda &>/dev/null; then
    USE_CONDA=1
fi

PIDS=()

cleanup() {
    echo ""
    echo "[Authority DEV] Shutting down..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM

# -------------------------------------------------------------------
# Start backend with --reload
# -------------------------------------------------------------------
echo "[Authority DEV] Starting backend (reload mode) on port $PORT..."

if [ "$USE_CONDA" = 1 ]; then
    conda run -n "$ENV_NAME" --no-banner --no-capture-output python -m uvicorn app.main:app \
        --host 127.0.0.1 --port "$PORT" --reload --app-dir "$BACKEND" &
else
    source "$ROOT/.venv/bin/activate" 2>/dev/null || true
    python -m uvicorn app.main:app \
        --host 127.0.0.1 --port "$PORT" --reload --app-dir "$BACKEND" &
fi
PIDS+=($!)

# -------------------------------------------------------------------
# Start Vite dev server
# -------------------------------------------------------------------
echo "[Authority DEV] Starting Vite dev server..."
(cd "$FRONTEND" && npm run dev) &
PIDS+=($!)

# -------------------------------------------------------------------
# Wait for backend, then print info
# -------------------------------------------------------------------
TRIES=0
while [ $TRIES -lt 20 ]; do
    sleep 2
    if curl -s -o /dev/null -w '%{http_code}' "http://localhost:$PORT/api/health" 2>/dev/null | grep -q 200; then
        break
    fi
    TRIES=$((TRIES + 1))
done

echo ""
echo "====================================================="
echo "  Authority DEV"
echo "  API:      http://localhost:$PORT/api"
echo "  Frontend: http://localhost:5173"
echo "  Docs:     http://localhost:$PORT/docs"
echo "====================================================="

if command -v xdg-open &>/dev/null; then xdg-open "http://localhost:5173"
elif command -v open &>/dev/null; then open "http://localhost:5173"
fi

# Keep alive until Ctrl+C
wait
