#!/usr/bin/env bash
# Start command of the Path.AI GPU pod. scripts/gpu.py sends it (with watchdog.py written next to it) when it creates
# or updates the pod; it runs again on every Start. It serves the model with vLLM (OpenAI-compatible API on port 8000)
# and keeps the watchdog in the foreground, which stops the pod when the model sits idle. If vLLM exits, port 8000
# shows the end of its log instead (to holders of the API key only), so `python -m scripts.gpu logs` can read why.
# --max-num-seqs: Qwen3.8 is a hybrid model that needs one state ("Mamba") cache block per running sequence; on a
# 48 GB card only ~240 fit, so vLLM's default of 256 parallel sequences refuses to start. 128 is plenty for us.
set -u
export HF_HOME="${HF_HOME:-/workspace/hf}"          # model weights on the pod volume: kept across Stop/Start
mkdir -p "$HF_HOME" /workspace/logs
LOG=/workspace/logs/vllm.log
echo "[start.sh] $(date -u +%FT%TZ) starting vLLM for $MODEL" >> "$LOG"
(
  vllm serve "$MODEL" --host 0.0.0.0 --port 8000 --served-model-name "$MODEL" \
    --max-model-len "${MAX_MODEL_LEN:-16384}" --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION:-0.92}" \
    --max-num-seqs "${MAX_NUM_SEQS:-128}" \
    --enable-prefix-caching --reasoning-parser qwen3 ${VLLM_EXTRA_ARGS:-} 2>&1 | tee -a "$LOG"
  echo "[start.sh] $(date -u +%FT%TZ) vLLM exited" | tee -a "$LOG"
  python3 - "$LOG" <<'PY'
import http.server, os, sys
log, key = sys.argv[1], os.environ.get("VLLM_API_KEY", "")
class Tail(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if not key or self.headers.get("Authorization") != f"Bearer {key}":
            self.send_response(401); self.end_headers(); return
        with open(log, errors="replace") as f:
            body = "\n".join(f.read().splitlines()[-300:]).encode()
        self.send_response(503); self.send_header("Content-Type", "text/plain; charset=utf-8"); self.end_headers(); self.wfile.write(body)
    def log_message(self, *args):
        pass
http.server.ThreadingHTTPServer(("0.0.0.0", 8000), Tail).serve_forever()
PY
) &
exec python3 /workspace/watchdog.py
