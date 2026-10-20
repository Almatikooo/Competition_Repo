"""Paths and environment settings. Reads an optional .env file (no extra dependency)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CATALOG_DIR = DATA / "catalog"
SIGNALS_DIR = DATA / "signals"
CACHE_DIR = DATA / "cache"
STATIC_DIR = ROOT / "static"


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

# Certificates: HMAC key that signs Path.AI certificates. Set it in production; changing it invalidates old links.
CERT_SECRET = os.getenv("CERT_SECRET", "")

# Trend sources.
OPENALEX_API_KEY = os.getenv("OPENALEX_API_KEY", "")
OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "")
HN_MONTHS = int(os.getenv("HN_MONTHS", "36"))
