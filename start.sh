#!/usr/bin/env bash
set -euo pipefail

# Authority — Mac/Linux launcher
# Starts the backend server. Run ./setup.sh first if dependencies changed.

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PORT=8700
ENV_NAME="authority"
BACKEND="$ROOT/src/backend"

# -------------------------------------------------------------------
# 1. Already running?
# -------------------------------------------------------------------
if curl -s -o /dev/null -w '%{http_code}' "http://localhost:$PORT/api/health" 2>/dev/null | grep -q 200; then
    echo "[Authority] Already running on port $PORT."
    if command -v xdg-open &>/dev/null; then xdg-open "http://localhost:$PORT"
    elif command -v open &>/dev/null; then open "http://localhost:$PORT"
    fi
    exit 0
fi

# -------------------------------------------------------------------
# 2. Resolve environment
# -------------------------------------------------------------------
USE_CONDA=0
if command -v conda &>/dev/null; then
    USE_CONDA=1
else
    if [ -f "$ROOT/.venv/bin/activate" ]; then
        # shellcheck disable=SC1091
        source "$ROOT/.venv/bin/activate"
    fi
fi

# -------------------------------------------------------------------
# 3. Start the backend
# -------------------------------------------------------------------
echo "[Authority] Starting on port $PORT..."

cleanup() {
    echo ""
    echo "[Authority] Shutting down..."
    kill "$BACKEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" 2>/dev/null || true
    exit 0
}
trap cleanup INT TERM

if [ "$USE_CONDA" = 1 ]; then
    conda run -n "$ENV_NAME" --no-capture-output python -m uvicorn app.main:app \
        --host 127.0.0.1 --port "$PORT" --workers 1 --reload --app-dir "$BACKEND" &
else
    python -m uvicorn app.main:app \
        --host 127.0.0.1 --port "$PORT" --workers 1 --reload --app-dir "$BACKEND" &
fi
BACKEND_PID=$!

# -------------------------------------------------------------------
# 4. Poll for readiness (up to 60s)
# -------------------------------------------------------------------
TRIES=0
while [ $TRIES -lt 30 ]; do
    sleep 2
    if curl -s -o /dev/null -w '%{http_code}' "http://localhost:$PORT/api/health" 2>/dev/null | grep -q 200; then
        break
    fi
    TRIES=$((TRIES + 1))
done

if [ $TRIES -ge 30 ]; then
    echo "[Authority] ERROR: Backend did not start within 60 seconds."
    echo "             Check logs/api.log for details."
    kill "$BACKEND_PID" 2>/dev/null || true
    exit 1
fi

# -------------------------------------------------------------------
# 5. Open browser
# -------------------------------------------------------------------
echo "[Authority] Ready at http://localhost:$PORT"
if command -v xdg-open &>/dev/null; then xdg-open "http://localhost:$PORT"
elif command -v open &>/dev/null; then open "http://localhost:$PORT"
fi

wait "$BACKEND_PID"
