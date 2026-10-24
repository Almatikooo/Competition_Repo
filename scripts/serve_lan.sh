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
echo "Path.AI is being served on your network. Share this address (type it with http://):"
echo "  http://${IP:-<this-computer-IP>}:${PORT}"
echo "  (or http://${NAME}.local:${PORT} on iPhones and Macs; Android and Windows often cannot resolve .local names)"
echo "Visitors must be on the same Wi-Fi. Keep this laptop on its charger with the lid open. Press Ctrl+C to stop."
# Long keep-alive: phones reuse idle connections, and a short server timeout makes some of those requests fail.
ARGS=(-m uvicorn app.main:app --app-dir src --host 0.0.0.0 --port "$PORT" --timeout-keep-alive 75)
if command -v caffeinate >/dev/null 2>&1; then
  exec caffeinate -is "$PY" "${ARGS[@]}"
fi
exec "$PY" "${ARGS[@]}"
