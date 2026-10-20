"""Checks that every learning resource, support portal and cited source URL is live.

Usage:  python scripts/verify_resources.py
Some sites (Kaggle, Khan Academy, WEF) answer bots with a challenge page; those are reported as 'bot-check'
and should be confirmed by hand once. Exit code 1 if any URL returns 404/410 or cannot be reached.
"""
import asyncio
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/129.0 Safari/537.36"}
CHALLENGE = ("checking your browser", "client challenge", "just a moment", "access denied")


def urls() -> list[tuple[str, str]]:
    res = json.loads((ROOT / "data/catalog/resources.json").read_text())
    src = json.loads((ROOT / "data/catalog/sources.json").read_text())
    out = [(r["id"], r["url"]) for r in res["resources"] + res["support"]]
    out += [(k, v["url"]) for k, v in src["sources"].items()]
    return out


async def check(client: httpx.AsyncClient, sem: asyncio.Semaphore, rid: str, url: str) -> tuple[str, str, str]:
    async with sem:
        try:
            resp = await client.get(url)
            head = resp.text[:3000].lower() if "text/html" in resp.headers.get("content-type", "") else ""
            if any(c in head for c in CHALLENGE) or resp.status_code in (401, 403):
                return rid, "bot-check", url
            return rid, "ok" if resp.status_code < 400 else f"HTTP {resp.status_code}", url
        except httpx.HTTPError as exc:
            return rid, f"error {type(exc).__name__}", url


async def main() -> int:
    sem = asyncio.Semaphore(8)
    async with httpx.AsyncClient(headers=UA, follow_redirects=True, timeout=25) as client:
        results = await asyncio.gather(*(check(client, sem, rid, url) for rid, url in urls()))
    bad = 0
    for rid, status, url in sorted(results, key=lambda r: (r[1] == "ok", r[0])):
        print(f"{status:12s} {rid:28s} {url}")
        bad += status not in ("ok", "bot-check")
    print(f"\n{len(results)} URLs checked, {bad} broken")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
