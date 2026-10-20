"""Cached, polite fetching for open course sources (GitHub, GOV.UK, Pressbooks, plain web pages)."""
import hashlib
import json
import subprocess
import time
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data/cache/learn/raw"
BOT_UA = "PathAI-Hackathon/0.1 (+https://github.com/Almatikooo/Competition_Repo; open course import)"
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36"

_client = httpx.Client(timeout=60, follow_redirects=True)


def _cache_path(key: str) -> Path:
    return CACHE / (hashlib.sha1(key.encode()).hexdigest() + ".txt")


def get_text(url: str, browser: bool = False, refresh: bool = False) -> str:
    """GET with an on-disk cache. Falls back to curl (system trust store) when Python's TLS stack refuses a site."""
    path = _cache_path(url)
    if path.exists() and not refresh:
        return path.read_text(encoding="utf-8")
    headers = {"User-Agent": BROWSER_UA if browser else BOT_UA, "Accept-Language": "en"}
    text, last_error = None, None
    for attempt in range(4):
        try:
            resp = _client.get(url, headers=headers)
            if resp.status_code == 200:
                text = resp.text
                break
            last_error = f"HTTP {resp.status_code}"
            if resp.status_code in (403, 404, 410):
                break
        except httpx.HTTPError as exc:
            last_error = f"{type(exc).__name__}: {exc}"
        time.sleep(2.5 * (attempt + 1))
    if text is None:  # e.g. certificate chains missing from certifi
        out = subprocess.run(["curl", "-sL", "--max-time", "60", "-A", headers["User-Agent"], "-w", "\n__HTTP__%{http_code}", url],
                             capture_output=True, text=True)
        body, _, status = out.stdout.rpartition("\n__HTTP__")
        if status.strip() == "200" and body:
            text = body
        else:
            raise RuntimeError(f"fetch failed for {url}: {last_error}; curl status {status.strip() or out.returncode}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    time.sleep(0.2)
    return text


def get_json(url: str, browser: bool = False) -> dict | list:
    return json.loads(get_text(url, browser=browser))


@lru_cache(maxsize=None)
def gh_sha(repo: str) -> str:
    """Pin every GitHub source to the commit we imported (recorded for attribution and reproducibility)."""
    pinned = ROOT / "data/learn/pins.json"
    pins = json.loads(pinned.read_text()) if pinned.exists() else {}
    if repo in pins:
        return pins[repo]
    out = subprocess.run(["gh", "api", f"repos/{repo}/commits/HEAD", "--jq", ".sha"], capture_output=True, text=True, check=True)
    sha = out.stdout.strip()
    pins[repo] = sha
    pinned.parent.mkdir(parents=True, exist_ok=True)
    pinned.write_text(json.dumps(pins, indent=1, sort_keys=True) + "\n")
    return sha


def gh_raw_url(repo: str, path: str) -> str:
    return f"https://raw.githubusercontent.com/{repo}/{gh_sha(repo)}/{quote(path)}"


def gh_blob_url(repo: str, path: str) -> str:
    return f"https://github.com/{repo}/blob/{gh_sha(repo)}/{quote(path)}"


def gh_file(repo: str, path: str) -> str:
    return get_text(gh_raw_url(repo, path))


def govuk(path: str) -> dict:
    return get_json("https://www.gov.uk/api/content" + path)


def pressbooks_chapter(book: str, slug: str) -> dict:
    """`book` is 'host/book' (e.g. 'openoregon.pressbooks.pub/beginningexcel19'); a bare name means opentextbc.ca (BCcampus)."""
    base = book if "/" in book else f"opentextbc.ca/{book}"
    items = get_json(f"https://{base}/wp-json/pressbooks/v2/chapters?slug={quote(slug)}", browser=True)
    if not items:
        raise RuntimeError(f"pressbooks chapter not found: {base}/{slug}")
    return items[0]
