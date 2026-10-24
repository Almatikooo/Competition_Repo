# Language model on RunPod: model choice, GPU choice and setup ($25 budget)

**TL;DR**

| | Choice |
|---|---|
| Model | **`Qwen/Qwen3.8-27B-FP8`**: open weights, Apache-2.0, released Aug 2026, served with vLLM |
| GPU | **1× RTX A6000 48 GB**, Secure Cloud **$0.59/h** (Community $0.33/h), so $25 buys about **40 GPU-hours** |
| Fallback | The app runs fully without the model (rule-based mode). Ranking, radar and pathways never depend on the LLM |

Prices come from runpod.io/pricing as checked on 2026-10-20. They change, so check again before you deploy.

## What the model does in Path.AI (and what it never does)

1. **CV to skills.** The output is JSON-schema constrained to our 53 skill ids, and every skill must quote the CV verbatim. If a quote cannot be found in the CV, the skill is dropped (`src/app/llm/tasks.py`).
2. **Grounded explanations** in English, Bahasa Malaysia or Chinese. The model only sees a fact sheet and must cite `[S1]…`. Any number that is not in the fact sheet makes the system fall back to the deterministic text.
3. **Reading job postings, once.** Each posting is trimmed to its requirement sentences (`scripts/opportunities/trim.py`) and numbered. The model returns skills (required or nice to have), years of experience, degree, languages, pay, work mode and visa sponsorship, each citing a sentence number. A fact is dropped unless its sentence contains the number, currency, language or degree word it claims (`scripts/opportunities/enrich.py`). Only the facts are kept (`data/opportunities/job_facts.json`).

The model never picks jobs, courses or statistics. Those come from the curated catalogs and the scoring engine.

## Why Qwen3.8-27B

- **License.** Apache-2.0, with no usage restrictions.
- **Fits one 48 GB GPU.** The official FP8 checkpoint is **30.9 GB**. The architecture is a hybrid (Gated DeltaNet + gated attention), and only 16 of its 64 layers use full attention, with 4 KV heads × 256 dims. That is about **64 KB of KV cache per token** (bf16), so the ~10–12 GB left on a 48 GB card holds well over 100K tokens of context. Long CVs and fact sheets are cheap.
- **Native vision-language.** It can read scanned or photographed CVs (next step for the intake).
- **Structured and agentic tasks.** It handles them well. vLLM enforces JSON schemas, and thinking can be switched off per request (`chat_template_kwargs: {"enable_thinking": false}`) for fast extraction.
- **Multilingual.** Malaysia needs English, Bahasa Malaysia and Chinese, and the Qwen family is native in Chinese. For the best Bahasa Malaysia, **`aisingapore/Qwen-SEA-LION-v4.5-27B-IT`** (MIT; base Qwen3.6-27B; lists ms, zh, ta) is a drop-in replacement with the same architecture and the same GPU.
- **Mature ecosystem.** It is the most-used open model of its size on Hugging Face (about 18K likes and 7.5M downloads within weeks), with official vLLM, SGLang and TokenSpeed recipes, so you hit fewer surprises at a hackathon.

### Alternatives considered

| Model | Why not, for this project |
|---|---|
| `openai/gpt-oss-20b` (Aug 2025, Apache-2.0) | Older, text-only, weaker in Malay and Chinese |
| `openai/gpt-oss-120b` | Needs an 80 GB GPU (≥ $1.19–1.79/h) |
| `google/gemma-4-31B-it` (Apache-2.0) | A solid alternative, but 31B dense leaves less KV headroom on 48 GB |
| `Qwen/Qwen3.6-35B-A3B` (MoE, Apache-2.0) | Generates 3–4× faster (3B active) but is weaker. This is the **speed fallback** on the same GPU |
| `Qwen/Qwen3.8-Flash-Next` | 180B params and a non-Apache license, too big for $25 |
| Mistral Small 4 / Medium 3.5, Llama 4 | ≥ 119B params: multi-GPU or ≥ 80 GB |
| `aisingapore/Nemotron-SEA-LION-v4.8-30B-A3B` | Great for SEA languages, but brand-new (few downloads) and lists no Chinese |

## Why an RTX A6000

The model needs 30.9 GB of weights plus KV cache plus activations, so at least about 40 GB. That means the 48 GB class.

| GPU | VRAM | Secure $/h | Community $/h | Hours for $25 (Secure) | Qwen3.8-27B-FP8 |
|---|---|---|---|---|---|
| RTX 4090 | 24 GB | 0.89 | 0.34 | 28 | does not fit (4-bit only) |
| RTX 5090 | 32 GB | 1.19 | 0.69 | 21 | tight (NVFP4 only) |
| **RTX A6000** | **48 GB** | **0.59** | **0.33** | **≈ 42** | **fits** |
| A40 | 48 GB | 0.59 | 0.35 | ≈ 42 | fits |
| L40S | 48 GB | 1.09 | 0.79 | ≈ 23 | fits (native FP8) |
| A100 80 GB | 80 GB | 1.79 | 1.19 | ≈ 14 | fits (overkill) |
| H100 SXM | 80 GB | 3.99 | 2.69 | ≈ 6 | fits (overkill) |

- The A6000 is the **cheapest 48 GB GPU** on RunPod, tied with the A40.
- Token generation is limited by memory bandwidth (A6000 768 GB/s vs L40S 864 GB/s), so the A6000 is only about 12% slower than an L40S at roughly half the price. Our load is a few users and short prompts.
- The A6000 is Ampere and has no native FP8. vLLM runs FP8 checkpoints as weight-only **W8A16 with Marlin kernels**, a supported path according to the vLLM docs. Check the startup log for the selected kernel.

**$25 budget plan (≈42 GPU hours).** The GPU runs only when it is needed and stops itself when idle:

| Use | GPU hours |
|---|---|
| First start (downloads the 31 GB model) and checks | ≈1 |
| Prompt checks for CV reading, explanations and job postings | ≈3–4 |
| Reading every job posting once (≈19.5k, `scripts/opportunities/enrich.py`) | ≈3 (estimate; the 300-posting pilot measures it) |
| Later features, demo rehearsals, video and the final round | the rest |

- **Stop the pod whenever it is idle** (`python -m scripts.gpu stop`). GPU billing stops; the 40 GB volume with the weights costs ≈$0.27/day while stopped. The watchdog stops a forgotten pod after 20 minutes without requests.
- **Community Cloud** is about 45% cheaper, but has fewer free GPUs. Use Secure Cloud for the live demo.
- **Serverless** charges per second ($1.22/h in the A6000/A40 class) but cold-starts by loading 31 GB, so it does not suit a demo.

**Fallbacks**

- FP8 does not load on Ampere: use an L40 or L40S (native FP8), a W8A16 INT8 community checkpoint, or `Qwen3.6-35B-A3B` AWQ (4-bit, and faster).
- RunPod has no free GPU for the stopped pod: `python -m scripts.gpu recreate` makes a new pod (it downloads the model again). Or try A40, then L40 ($0.82/h), then L40S ($1.09/h) by setting `GPU_TYPE` in `.env`.
- GPU down during the demo: Path.AI keeps working in rule-based mode, with the answers and job facts the model already gave.

## Step by step: one command

1. In RunPod, open **Settings → API Keys**, create a key and put it in `.env` as `RUNPOD_API_KEY=…`. Never commit it or paste it anywhere else.
2. `python -m scripts.gpu create`. It creates the pod: **RTX A6000** on Secure Cloud, image `vllm/vllm-openai:v0.31.0`, a 40 GB volume at `/workspace` for the weights, HTTP port 8000, and the start command from `deploy/runpod/` (vLLM plus the watchdog). It writes `RUNPOD_POD_ID`, `LLM_BASE_URL`, `LLM_API_KEY` (a fresh secret for vLLM) and `LLM_MODEL` into `.env`.
3. `python -m scripts.gpu wait`. The first start downloads about 31 GB; later starts take about 3–5 minutes.
4. Restart Path.AI. The footer says the AI is on, CV parsing uses the model behind the evidence guardrail, every role card gets **Rewrite with AI**, and `python -m scripts.opportunities.enrich` can read the job postings.
5. `python -m scripts.gpu stop` when you finish. `status` shows uptime, this session's cost and the balance left.
6. Changed `deploy/runpod/` or a setting? `python -m scripts.gpu update` sends it to the pod (it restarts; the weights stay). If vLLM ever stops, `python -m scripts.gpu logs` prints the end of its log.
7. Reading every job posting: `caffeinate -is python -m scripts.opportunities.enrich --concurrency 64 --then-stop` keeps the laptop awake, continues after a dropped connection and switches the GPU off at the end. Measured: ≈100 postings a minute at 32 in parallel.

**The watchdog** (`deploy/runpod/watchdog.py`) runs inside the pod. It stops the pod after `IDLE_MINUTES` (20) without a request to the model, when the model does not come up within 40 minutes, or after 10 hours in all. It uses the pod-scoped `RUNPOD_API_KEY` and `RUNPOD_POD_ID` that RunPod sets in every pod, so your account key never leaves your laptop.

**Manual setup in the console (option A).**

1. Go to **Pods → Deploy**, pick **RTX A6000** on **Secure Cloud**.
2. Set the container image to **`vllm/vllm-openai:v0.31.0`** (Qwen3.8 needs vLLM ≥ 0.17).
3. Give the pod a **40 GB volume** mounted at `/workspace` and set `HF_HOME=/workspace/hf`, so the weights survive Stop/Start.
4. **Expose HTTP port 8000.**
5. Set the container start command. Replace `CHANGE_ME` with a long random secret:

   ```
   vllm serve Qwen/Qwen3.8-27B-FP8 --host 0.0.0.0 --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.92 --max-num-seqs 128 --reasoning-parser qwen3 --enable-prefix-caching --api-key CHANGE_ME
   ```

   - Keep `--max-num-seqs 128`. Qwen3.8 is a hybrid model that needs one state ("Mamba") cache block per running sequence; on 48 GB only about 240 fit, so vLLM's default of 256 stops with `max_num_seqs (256) exceeds available Mamba cache blocks`.

   - If the log says `unrecognized arguments`, the image's entrypoint already includes `vllm serve`. Delete those two words.
   - Optional: `--language-model-only` skips the vision encoder and frees memory.
   - Optional: MTP speculative decoding, `--speculative-config '{"method":"mtp","num_speculative_tokens":3}'`, if your vLLM build supports it.
6. Wait for `Application startup complete` in **Logs**, then smoke-test:

   ```bash
   curl https://<POD_ID>-8000.proxy.runpod.net/v1/models -H "Authorization: Bearer CHANGE_ME"
   ```

7. Put `LLM_BASE_URL=https://<POD_ID>-8000.proxy.runpod.net/v1`, `LLM_API_KEY=CHANGE_ME` and `LLM_MODEL=Qwen/Qwen3.8-27B-FP8` in `.env`. This manual pod has no watchdog: **stop it yourself** when you finish.

**Option B, with no image entrypoint questions.** Use the PyTorch template, open a web terminal, run `pip install -U vllm`, then run the same `vllm serve …` command. Expose port 8000 in the pod settings.

**Option C, Serverless.** Go to Serverless and use the vLLM quick deploy. Set `MODEL_NAME=Qwen/Qwen3.8-27B-FP8`, `MAX_MODEL_LEN=32768`, and a 48 GB GPU. Then use `LLM_BASE_URL=https://api.runpod.ai/v2/<ENDPOINT_ID>/openai/v1` with your RunPod API key as `LLM_API_KEY`.

**Before the GPU arrives,** any OpenAI-compatible local server works for testing, for example Ollama (`http://localhost:11434/v1`) or LM Studio running a small Qwen. The guardrail tests in `tests/test_guardrails.py` use a fake vLLM endpoint, so they need no GPU at all.
