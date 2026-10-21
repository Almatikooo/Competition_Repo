"""Polite cached GETs for the open job feeds (raw responses kept in data/cache, which is git-ignored)."""
import hashlib
import json
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/cache/opportunities/raw"
USER_AGENT = "PathAI/0.1 (SDC XMUM hackathon prototype; education project; github.com/Almatikooo)"
MAX_AGE_HOURS = 20


def _path(url: str) -> Path:
    return RAW / f"{hashlib.sha1(url.encode()).hexdigest()[:20]}.json"


def get_json(client: httpx.Client, url: str, max_age_hours: float = MAX_AGE_HOURS, pause: float = 0.4):
    path = _path(url)
    if path.exists() and time.time() - path.stat().st_mtime < max_age_hours * 3600:
        return json.loads(path.read_text(encoding="utf-8"))
    for attempt in range(3):
        resp = client.get(url)
        if resp.status_code == 429 and attempt < 2:
            time.sleep(10 * (attempt + 1))
            continue
        resp.raise_for_status()
        break
    data = resp.json()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    time.sleep(pause)
    return data


def client() -> httpx.Client:
    return httpx.Client(timeout=90, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, follow_redirects=True)
