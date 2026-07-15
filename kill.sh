#!/usr/bin/env bash
set -euo pipefail

# Authority — stop any running instance (Mac/Linux)

PORT=8700

echo "[Authority] Looking for processes on port $PORT..."

PIDS=$(lsof -ti ":$PORT" 2>/dev/null || true)

if [ -z "$PIDS" ]; then
    echo "[Authority] Nothing running on port $PORT."
    exit 0
fi

for pid in $PIDS; do
    echo "[Authority] Killing PID $pid"
    kill "$pid" 2>/dev/null || true
done

sleep 1

if curl -s -o /dev/null -w '%{http_code}' "http://localhost:$PORT/api/health" 2>/dev/null | grep -q 200; then
    echo "[Authority] WARNING: Port $PORT still in use. You may need to close it manually."
else
    echo "[Authority] Stopped."
fi
