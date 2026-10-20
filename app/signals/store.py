"""Small JSON persistence helpers for trend signals (atomic writes, UTC timestamps)."""
import datetime as dt
import hashlib
import json
from pathlib import Path

from ..config import CACHE_DIR, SIGNALS_DIR

HN_FILE = SIGNALS_DIR / "hn_monthly.json"
OPENALEX_FILE = SIGNALS_DIR / "openalex.json"
META_FILE = SIGNALS_DIR / "meta.json"
HN_RAW_DIR = CACHE_DIR / "hn"


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def stable_hash(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True).encode()).hexdigest()[:12]
