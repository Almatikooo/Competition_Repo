"""Paths and environment settings. Reads an optional .env file (no extra dependency)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # the repository: data/, .env, docs/
SRC = Path(__file__).resolve().parents[1]           # src/: the app (app/) and the web pages (static/)
DATA = ROOT / "data"
CATALOG_DIR = DATA / "catalog"
SIGNALS_DIR = DATA / "signals"
CACHE_DIR = DATA / "cache"
STATIC_DIR = SRC / "static"


def _load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

# Language model: any OpenAI-compatible endpoint (vLLM on a RunPod pod/serverless, Ollama, LM Studio).
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen3.8-27B-FP8")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "90"))
# Qwen3.x thinks by default; structured extraction is faster and more reliable without it.
LLM_DISABLE_THINKING = os.getenv("LLM_DISABLE_THINKING", "true").lower() == "true"
# One GPU serves everyone: the web app sends at most this many requests at a time (batch jobs set their own limit).
LLM_MAX_PARALLEL = int(os.getenv("LLM_MAX_PARALLEL", "4"))
# Backup model while our own GPU is off: a hosted copy of the same open model (Groq serves qwen/qwen3.8-27b on an
# OpenAI-compatible API). It gets the facts behind an answer, never a CV, and batch scripts never use it.
LLM_BACKUP_BASE_URL = os.getenv("LLM_BACKUP_BASE_URL", "").rstrip("/")
LLM_BACKUP_API_KEY = os.getenv("LLM_BACKUP_API_KEY", "")
LLM_BACKUP_MODEL = os.getenv("LLM_BACKUP_MODEL", "qwen/qwen3.8-27b")
# Model answers are kept, so the same request is answered at once and without the GPU: data/cache/llm (local)
# and data/ai/answers.jsonl (saved answers for the example people, committed so the demo shows them with the GPU off).
LLM_CACHE_DIR = CACHE_DIR / "llm"
LLM_SAVED_ANSWERS = DATA / "ai" / "answers.jsonl"

# Accounts (optional): sign in with Google to keep progress across devices. Without these, the site runs guest-only.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
ACCOUNTS_DB = Path(os.getenv("ACCOUNTS_DB", str(CACHE_DIR / "accounts.sqlite3")))

# Certificates: HMAC key that signs Path.AI certificates. Set it in production; changing it invalidates old links.
CERT_SECRET = os.getenv("CERT_SECRET", "")

# Trend sources.
OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY", "")
OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "")
HN_MONTHS = int(os.getenv("HN_MONTHS", "36"))
