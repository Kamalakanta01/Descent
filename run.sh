#!/usr/bin/env bash
# Descent — one command to run the whole app.
# Creates the venv + installs deps on first run; then serves API + frontend
# with auto-reload on 127.0.0.1:8000. Ctrl-C to stop.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${1:-8000}"

if [ ! -x .venv/bin/python ]; then
  echo "==> creating venv"
  python3 -m venv .venv
  echo "==> installing backend deps"
  .venv/bin/pip install -q -r backend/requirements.txt
fi

echo "==> serving on http://127.0.0.1:$PORT  (Ctrl-C to stop)"
cd backend
exec ../.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --reload