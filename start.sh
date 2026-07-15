#!/usr/bin/env bash
set -euo pipefail

# Authority — Mac/Linux production launcher (doc 02)
# Usage: ./start.sh    Ctrl+C to stop.

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

PORT=8700
ENV_NAME="authority"
BACKEND="$ROOT/src/backend"
FRONTEND="$ROOT/src/frontend"
MARKER="$ROOT/.setup-complete"

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
# 2. Environment resolution (conda preferred, else venv)
# -------------------------------------------------------------------
USE_CONDA=0
if command -v conda &>/dev/null; then
    USE_CONDA=1
    echo "[Authority] Using conda environment \"$ENV_NAME\""
    if ! conda info --envs 2>/dev/null | grep -q "$ENV_NAME"; then
        echo "[Authority] Creating conda environment \"$ENV_NAME\" with Python 3.11..."
        conda create -n "$ENV_NAME" python=3.11 -y
    fi
else
    echo "[Authority] conda not found; using venv at .venv"
    if [ ! -f "$ROOT/.venv/bin/activate" ]; then
        python3 -m venv "$ROOT/.venv"
    fi
    # shellcheck disable=SC1091
    source "$ROOT/.venv/bin/activate"
fi

run_python() {
    if [ "$USE_CONDA" = 1 ]; then
        conda run -n "$ENV_NAME" --no-banner --no-capture-output "$@"
    else
        "$@"
    fi
}

# -------------------------------------------------------------------
# 3. First-run setup
# -------------------------------------------------------------------
HASH="$(md5sum "$BACKEND/requirements.txt" "$FRONTEND/package.json" 2>/dev/null | md5sum | cut -d' ' -f1)"

NEED_SETUP=0
if [ ! -f "$MARKER" ]; then
    NEED_SETUP=1
elif [ "$(cat "$MARKER")" != "$HASH" ]; then
    NEED_SETUP=1
fi

if [ "$NEED_SETUP" = 1 ]; then
    echo "[Authority] Installing / updating dependencies..."

    run_python pip install -r "$BACKEND/requirements.txt"

    if ! command -v git &>/dev/null; then
        echo "[Authority] WARNING: git is not installed. Version control features will not work."
    fi

    echo "[Authority] Building frontend..."
    (cd "$FRONTEND" && npm install && npm run build)

    echo "$HASH" > "$MARKER"
    echo "[Authority] Setup complete."
fi

# -------------------------------------------------------------------
# 4. Start the backend
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
    conda run -n "$ENV_NAME" --no-banner --no-capture-output python -m uvicorn app.main:app \
        --host 127.0.0.1 --port "$PORT" --workers 1 --app-dir "$BACKEND" &
else
    python -m uvicorn app.main:app \
        --host 127.0.0.1 --port "$PORT" --workers 1 --app-dir "$BACKEND" &
fi
BACKEND_PID=$!

# -------------------------------------------------------------------
# 5. Poll for readiness (up to 60s)
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
# 6. Open browser
# -------------------------------------------------------------------
echo "[Authority] Ready at http://localhost:$PORT"
if command -v xdg-open &>/dev/null; then xdg-open "http://localhost:$PORT"
elif command -v open &>/dev/null; then open "http://localhost:$PORT"
fi

# Keep alive
wait "$BACKEND_PID"
