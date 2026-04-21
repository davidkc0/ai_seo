#!/usr/bin/env bash
# Start AI Mention Tracker locally: backend on :8000, frontend on :5173.
# Kills both on Ctrl-C.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

# --- Preflight ------------------------------------------------------------

if [ ! -d "$BACKEND/venv" ]; then
  echo "[start.sh] No venv found at $BACKEND/venv"
  echo "[start.sh] Create one with:"
  echo "           cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

if [ ! -f "$BACKEND/.env" ]; then
  echo "[start.sh] Missing $BACKEND/.env — copy .env.example and fill in keys. See SETUP.md."
  exit 1
fi

if [ ! -d "$FRONTEND/node_modules" ]; then
  echo "[start.sh] No node_modules — running npm install..."
  (cd "$FRONTEND" && npm install)
fi

# --- Launch ---------------------------------------------------------------

echo "[start.sh] Starting backend on http://localhost:8000"
(
  cd "$BACKEND"
  # shellcheck source=/dev/null
  source venv/bin/activate
  python main.py
) &
BACKEND_PID=$!

echo "[start.sh] Starting frontend on http://localhost:5173"
(
  cd "$FRONTEND"
  npm run dev
) &
FRONTEND_PID=$!

# --- Cleanup on exit ------------------------------------------------------

cleanup() {
  echo ""
  echo "[start.sh] Shutting down..."
  kill "$BACKEND_PID" 2>/dev/null || true
  kill "$FRONTEND_PID" 2>/dev/null || true
  wait 2>/dev/null || true
  echo "[start.sh] Done."
}
trap cleanup INT TERM EXIT

echo "[start.sh] Both running. Ctrl-C to stop."
wait
