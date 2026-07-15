#!/usr/bin/env bash
set -euo pipefail

# Authority — Mac/Linux setup script
# Installs Python deps, Node deps, builds frontend.
# Run once after cloning, or again after changing requirements.txt / package.json.

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

ENV_NAME="authority"
BACKEND="$ROOT/src/backend"
FRONTEND="$ROOT/src/frontend"

# -------------------------------------------------------------------
# 1. Resolve Python environment (conda preferred, else venv)
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
        conda run -n "$ENV_NAME" --no-capture-output "$@"
    else
        "$@"
    fi
}

# -------------------------------------------------------------------
# 2. Install Python dependencies
# -------------------------------------------------------------------
echo "[Authority] Installing Python dependencies..."
run_python pip install -r "$BACKEND/requirements.txt" || true

if ! run_python python -c "import fastapi" 2>/dev/null; then
    echo "[Authority] ERROR: pip install failed."
    exit 1
fi
echo "[Authority] Python dependencies OK."

# -------------------------------------------------------------------
# 3. Check git
# -------------------------------------------------------------------
if ! command -v git &>/dev/null; then
    echo "[Authority] WARNING: git is not installed. Version control features will not work."
fi

# -------------------------------------------------------------------
# 4. Install Node dependencies + build frontend
# -------------------------------------------------------------------
echo "[Authority] Installing Node dependencies..."
(cd "$FRONTEND" && npm install)

echo "[Authority] Building frontend..."
(cd "$FRONTEND" && npm run build)

echo ""
echo "[Authority] Setup complete. Run ./start.sh to launch."
