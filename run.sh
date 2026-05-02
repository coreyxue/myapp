#!/usr/bin/env bash
# ComicForge launcher for macOS / Linux.
set -euo pipefail
cd "$(dirname "$0")"

PY=${PY:-python3}
PORT=${PORT:-8765}
export COMICFORGE_LLM=${COMICFORGE_LLM:-ollama}

if [ ! -d .venv ]; then
    echo "[setup] creating venv..."
    "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

if ! python -c "import comicforge" >/dev/null 2>&1; then
    echo "[setup] installing dependencies..."
    python -m pip install --upgrade pip >/dev/null
    python -m pip install -e .
fi

URL="http://127.0.0.1:${PORT}"
echo "[run] $URL"
case "$(uname -s)" in
    Darwin*) open "$URL" >/dev/null 2>&1 || true ;;
    Linux*)  xdg-open "$URL" >/dev/null 2>&1 || true ;;
esac
exec python -m uvicorn comicforge.server:app --host 127.0.0.1 --port "$PORT"
