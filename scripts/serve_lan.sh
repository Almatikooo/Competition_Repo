#!/usr/bin/env bash
# Serve Path.AI to everyone on the same Wi-Fi / local network:   bash scripts/serve_lan.sh [port]
# Prints the addresses to share, keeps the computer awake while it runs (macOS) and stops with Ctrl+C.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${1:-8080}"
PY=".venv/bin/python"
[ -x "$PY" ] || PY="python3"
IP="$({ ipconfig getifaddr en0 || ipconfig getifaddr en1 || hostname -I | awk '{print $1}'; } 2>/dev/null | head -1 || true)"
NAME="$(scutil --get LocalHostName 2>/dev/null || hostname -s)"
echo "Path.AI is being served on your network. Share one of these:"
echo "  http://${IP:-<this-computer-IP>}:${PORT}"
echo "  http://${NAME}.local:${PORT}"
echo "Visitors must be on the same Wi-Fi. Press Ctrl+C to stop."
if command -v caffeinate >/dev/null 2>&1; then
  exec caffeinate -is "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
fi
exec "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
