#!/usr/bin/env bash
# Start command of the Path.AI GPU pod. scripts/gpu.py sends it (with watchdog.py written next to it) when it creates
# the pod; it runs again on every Start. It serves the model with vLLM (OpenAI-compatible API on port 8000) and keeps
# the watchdog in the foreground, which stops the pod when the model sits idle.
set -u
export HF_HOME="${HF_HOME:-/workspace/hf}"          # model weights on the pod volume: kept across Stop/Start
mkdir -p "$HF_HOME" /workspace/logs
vllm serve "$MODEL" --host 0.0.0.0 --port 8000 --served-model-name "$MODEL" \
  --max-model-len "${MAX_MODEL_LEN:-16384}" --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION:-0.92}" \
  --enable-prefix-caching --reasoning-parser qwen3 ${VLLM_EXTRA_ARGS:-} 2>&1 | tee -a /workspace/logs/vllm.log &
exec python3 /workspace/watchdog.py
