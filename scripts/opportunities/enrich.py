"""Path.AI reads every job posting once with the language model (Qwen on the GPU) and keeps facts only.

    python -m scripts.opportunities.enrich --dry-run       # what is left to read: tokens, hours and cost (no GPU needed)
    python -m scripts.opportunities.enrich --limit 300     # a pilot: the first 300 by priority
    python -m scripts.opportunities.enrich                 # everything not read yet
    python -m scripts.opportunities.enrich --eval          # accuracy on the hand-checked gold set
    caffeinate -is python -m scripts.opportunities.enrich --then-stop   # read everything, then switch the GPU off

Input: the trimmed posting texts that jobs.py writes to data/cache/opportunities/texts.jsonl (they never leave the cache).
The model sees each posting as numbered sentences and returns facts that each cite a sentence NUMBER. A guard drops
every fact whose sentence does not exist or does not contain what the fact claims (the number of years, the pay amounts
and currency, the language, the degree, the work mode, the visa wording). Output: data/opportunities/job_facts.json,
keyed by a stable hash of the posting URL and merged into the jobs by app/opportunities.py.

Order: Malaysia, Singapore, remote jobs open to Malaysia, then the rest, newest first. Progress is saved after every
posting, so when the GPU stops (or the watchdog stops it) nothing is lost: run the command again to continue.
"""
import argparse
import asyncio
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.catalog import get_catalog  # noqa: E402
from app.llm.client import LLMClient, LLMUnavailable  # noqa: E402

CACHE = ROOT / "data/cache/opportunities"
TEXTS = CACHE / "texts.jsonl"
PROGRESS = CACHE / "facts_progress.jsonl"
GOLD = CACHE / "gold.json"
JOBS = ROOT / "data/opportunities/jobs.json"
OUT = ROOT / "data/opportunities/job_facts.json"

PRICE_PER_HOUR = 0.59                          # RTX A6000, RunPod Secure Cloud
PREFILL_TOK_S, DECODE_TOK_S = 1250, 700        # A6000 + Qwen3.8-27B-FP8 guesses, replaced by the pilot's measured speed
OUTPUT_TOKENS = 130                            # per posting: compact facts with sentence numbers (measured 80–160)

LEVELS = ["secondary", "diploma", "bachelor", "master", "phd"]
DEGREE = {"secondary": ["high school", "secondary", "spm", "stpm", "o level", "a level", "o-level", "a-level", "gcse"],
          "diploma": ["diploma", "associate degree", "associate's", "hnd", "vocational"],
          "bachelor": ["bachelor", "degree", "bsc", "b.sc", "b.s.", "b.a.", "beng", "b.eng", "undergraduate", "graduate",
                       "ijazah", "sarjana muda", "学士", "本科"],
          "master": ["master", "msc", "m.sc", "mba", "m.s.", "meng", "postgraduate", "sarjana", "硕士"],
          "phd": ["phd", "ph.d", "doctorate", "doctoral", "doktor falsafah", "博士"]}
LANGS = {"en": ["english", "inggeris"], "ms": ["malay", "melayu", "bahasa malaysia", "bahasa"], "zh": ["mandarin", "chinese", "中文", "普通话", "华语", "cina"],
         "yue": ["cantonese", "粤语", "廣東話"], "ta": ["tamil"], "hi": ["hindi"], "ja": ["japanese", "日本語"], "ko": ["korean", "한국어"],
         "th": ["thai"], "vi": ["vietnamese"], "id": ["indonesian", "bahasa indonesia"], "tl": ["tagalog", "filipino"], "ar": ["arabic"],
         "de": ["german", "deutsch"], "fr": ["french", "français", "francais"], "es": ["spanish", "español", "espanol"],
         "pt": ["portuguese", "português"], "it": ["italian", "italiano"], "nl": ["dutch", "nederlands"], "pl": ["polish", "polski"],
         "sv": ["swedish", "svenska"], "da": ["danish", "dansk"], "no": ["norwegian", "norsk"], "fi": ["finnish", "suomi"],
         "tr": ["turkish", "türkçe"], "ru": ["russian"], "uk": ["ukrainian"], "cs": ["czech"], "he": ["hebrew"], "el": ["greek"],
         "ro": ["romanian"], "hu": ["hungarian"]}
CURRENCIES = {"MYR": ["rm", "myr", "ringgit"], "SGD": ["s$", "sgd"], "USD": ["$", "usd"], "EUR": ["€", "eur", "euro"], "GBP": ["£", "gbp"],
              "AUD": ["a$", "au$", "aud"], "CAD": ["c$", "ca$", "cad"], "HKD": ["hk$", "hkd"], "NZD": ["nz$", "nzd"],
              "INR": ["₹", "inr", "rs", "lakh", "lpa"], "JPY": ["¥", "jpy", "円", "yen"], "CNY": ["¥", "cny", "rmb", "元"], "CHF": ["chf"],
              "SEK": ["sek", "kr"], "NOK": ["nok", "kr"], "DKK": ["dkk", "kr"], "PLN": ["pln", "zł"], "IDR": ["idr", "rp"],
              "PHP": ["php", "₱"], "THB": ["thb", "฿"], "VND": ["vnd", "₫"], "KRW": ["krw", "₩"], "AED": ["aed"], "BRL": ["brl", "r$"],
              "MXN": ["mxn"], "ZAR": ["zar"], "CZK": ["czk", "kč"], "ILS": ["ils", "₪"]}
MODES = {"onsite": ["on-site", "onsite", "on site", "in office", "in-office", "office-based", "office based", "in person", "in-person", "at our office", "di pejabat"],
         "hybrid": ["hybrid"],
         "remote": ["remote", "work from home", "wfh", "work from anywhere", "fully distributed"]}
VISA = ["visa", "sponsor", "work permit", "right to work", "work authori", "relocat", "employment pass", "eligible to work", "citizen", "permanent resident"]
PERIODS = ["hour", "day", "month", "year"]
ZERO_EXPERIENCE = re.compile(
    r"\b(?:fresh|new|recent)\s+grad\w*|\bentry[- ]level\b|\bno (?:prior |previous )?(?:work )?experience|\bgraduates? (?:are )?welcome"
    r"|\bintern(?:ship)?s?\b|\bcurrently (?:pursuing|enrolled|studying)|\bstudents?\b|\bup to \d+ years?|\btiada pengalaman|\blepasan"
    r"|应届|无经验|实习", re.I)
NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5, "enam": 6, "tujuh": 7, "lapan": 8, "sembilan": 9, "sepuluh": 10}
NUM = re.compile(r"(\d+(?:[.,]\d+)*)(\s?[kK]\b)?")


# ---------------------------------------------------------------- the guard
def mentions(sentence: str, words: list[str]) -> bool:
    low = sentence.lower()
    for w in words:
        if re.fullmatch(r"[a-z .'-]+", w):
            if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low):
                return True
        elif w in low:
            return True
    return False


def numbers_in(sentence: str) -> set[float]:
    out: set[float] = set()
    for m in NUM.finditer(sentence):
        raw = m.group(1)
        for v in {raw.replace(",", ""), raw.replace(".", "").replace(",", ""), raw.replace(",", ".")}:
            try:
                x = float(v)
            except ValueError:
                continue
            out.add(x)
            if m.group(2):
                out.add(x * 1000)
    low = sentence.lower()
    out |= {float(n) for w, n in NUMBER_WORDS.items() if re.search(rf"\b{w}\b", low)}
    if re.search(r"\ban? (?:full )?years?\b", low):                  # "at least a year"
        out.add(1.0)
    return out


def has_number(sentence: str, value) -> bool:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return False
    return any(abs(x - value) <= max(0.005 * abs(value), 1e-9) for x in numbers_in(sentence))


def guard(sents: list[str], raw: dict, skill_ids: set[str]) -> tuple[dict, list[str]]:
    """Keeps only the facts whose cited sentence exists and says what the fact claims. Returns (facts, dropped)."""
    facts: dict = {}
    dropped: list[str] = []

    def cited(item) -> str | None:
        s = item.get("s") if isinstance(item, dict) else None
        return sents[s - 1] if isinstance(s, int) and not isinstance(s, bool) and 1 <= s <= len(sents) else None

    req, nice = [], []
    for item in raw.get("skills") or []:
        if item.get("id") in skill_ids and cited(item):
            (req if item.get("need") == "required" else nice).append(item["id"])
        else:
            dropped.append(f"skill:{item.get('id')}")
    req = list(dict.fromkeys(req))
    nice = [s for s in dict.fromkeys(nice) if s not in req]
    if req:
        facts["req"] = req
    if nice:
        facts["nice"] = nice

    if (y := raw.get("experience")) is not None:
        st = cited(y)
        years = y.get("min_years")
        zero_ok = years == 0 and st and ZERO_EXPERIENCE.search(st)       # "fresh graduates welcome", interns = 0 years
        if st and isinstance(years, int) and 0 <= years <= 25 and (has_number(st, years) or zero_ok):
            facts["years"] = years
        else:
            dropped.append("years")
    if (d := raw.get("degree")) is not None:
        st = cited(d)
        if st and d.get("level") in DEGREE and mentions(st, DEGREE[d["level"]]):
            facts["degree"] = d["level"]
            facts["degree_required"] = bool(d.get("required"))
        else:
            dropped.append("degree")
    langs = []
    for item in raw.get("languages") or []:
        st = cited(item)
        if st and item.get("code") in LANGS and mentions(st, LANGS[item["code"]]):
            langs.append(item["code"])
        else:
            dropped.append(f"language:{item.get('code')}")
    if langs:
        facts["languages"] = list(dict.fromkeys(langs))
    if (p := raw.get("pay")) is not None:
        st = cited(p)
        lo, hi = p.get("min"), p.get("max")
        ok = (st and p.get("currency") in CURRENCIES and mentions(st, CURRENCIES[p["currency"]]) and p.get("per") in PERIODS
              and isinstance(lo, (int, float)) and lo > 0 and has_number(st, lo)
              and (hi is None or (isinstance(hi, (int, float)) and hi >= lo and has_number(st, hi))))
        if ok:
            num = lambda x: int(x) if x is not None and float(x).is_integer() else x
            facts["pay"] = [num(lo), num(hi), p["currency"], p["per"]]
        else:
            dropped.append("pay")
    if (m := raw.get("work_mode")) is not None:
        st = cited(m)
        if st and m.get("value") in MODES and mentions(st, MODES[m["value"]]):
            facts["mode"] = m["value"]
        else:
            dropped.append("mode")
    if (v := raw.get("visa")) is not None:
        st = cited(v)
        if st and isinstance(v.get("sponsors"), bool) and mentions(st, VISA):
            facts["visa"] = v["sponsors"]
        else:
            dropped.append("visa")
    return facts, dropped


# ---------------------------------------------------------------- the request
def schema(skill_ids: list[str]) -> dict:
    cite = {"type": "integer"}

    def obj(props: dict) -> dict:
        return {"type": "object", "additionalProperties": False, "required": list(props), "properties": props}

    def nullable(o: dict) -> dict:
        return {"anyOf": [o, {"type": "null"}]}

    return obj({
        "skills": {"type": "array", "items": obj({"id": {"type": "string", "enum": skill_ids},
                                                  "need": {"type": "string", "enum": ["required", "nice"]}, "s": cite})},
        "experience": nullable(obj({"min_years": {"type": "integer"}, "s": cite})),   # named "years"/"min", the model left it null
        "degree": nullable(obj({"level": {"type": "string", "enum": LEVELS}, "required": {"type": "boolean"}, "s": cite})),
        "languages": {"type": "array", "items": obj({"code": {"type": "string", "enum": sorted(LANGS)}, "s": cite})},
        "pay": nullable(obj({"min": {"type": "number"}, "max": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                             "currency": {"type": "string", "enum": sorted(CURRENCIES)}, "per": {"type": "string", "enum": PERIODS}, "s": cite})),
        "work_mode": nullable(obj({"value": {"type": "string", "enum": sorted(MODES)}, "s": cite})),
        "visa": nullable(obj({"sponsors": {"type": "boolean"}, "s": cite})),
    })


def system_prompt(catalog) -> str:
    taxonomy = "\n".join(f"- {sid}: {s['name']['en']}" for sid, s in sorted(catalog.skills.items()))
    return (
        "You read one job posting and extract facts for a job-matching app. The posting is given as numbered sentences. "
        "Every fact must cite, in field \"s\", the number of the sentence that states it. Report only what the posting "
        "states explicitly; when something is not stated, use null or an empty list. Never guess.\n"
        "- skills: skills from the catalogue below that the job asks for. need = \"required\" when stated as a must, "
        "\"nice\" when stated as preferred, a plus or a bonus. Use only catalogue ids; leave out skills the catalogue lacks.\n"
        "- experience: the minimum years of work experience the posting asks for, e.g. \"3-5 years\" -> min_years 3, \"at least 2 years\" "
        "-> 2, \"fresh graduates welcome\" -> 0. Fill it whenever the posting states a number of years.\n"
        "- degree: the minimum education level asked for; required = false when it says preferred, or equivalent experience.\n"
        "- languages: human languages the job REQUIRES (not programming languages); leave out languages that are only a plus, "
        "preferred or beneficial.\n"
        "- pay: the pay as written: min, max (null when only one amount), currency as an ISO code, per hour/day/month/year. "
        "Copy the amounts exactly; expand k (\"120k\" -> 120000).\n"
        "- work_mode: onsite, hybrid or remote, when the posting says so (e.g. \"hybrid setup\", \"fully remote\", \"remote-first\").\n"
        "- visa: sponsors = true when visa sponsorship or relocation support is offered; false when it says no sponsorship "
        "or that applicants must already have the right to work.\n"
        "The posting may be in English, Bahasa Malaysia, Chinese or another language.\n"
        'Example of the format: {"skills":[{"id":"sql","need":"required","s":3},{"id":"python","need":"nice","s":5}],'
        '"experience":{"min_years":3,"s":2},"degree":{"level":"bachelor","required":true,"s":4},"languages":[{"code":"en","s":6}],'
        '"pay":{"min":4000,"max":6000,"currency":"MYR","per":"month","s":7},"work_mode":{"value":"hybrid","s":8},"visa":null}\n'
        "Reply with compact JSON on a single line: no line breaks, no indentation.\n\n"   # pretty-printing doubled the output
        f"Skills catalogue (id: name):\n{taxonomy}")


def user_prompt(row: dict) -> str:
    lines = "\n".join(f"[{i}] {s}" for i, s in enumerate(row["sentences"], 1))
    return f"Job title: {row['title']}\nCompany: {row['company']}\nSentences:\n{lines}"


class Reader:
    def __init__(self, client: LLMClient) -> None:
        self.catalog = get_catalog()
        self.skill_ids = sorted(self.catalog.skills)
        self.schema = schema(self.skill_ids)
        self.system = system_prompt(self.catalog)
        self.client = client

    async def read(self, row: dict) -> tuple[dict, list[str]]:
        if not row["sentences"]:
            return {}, []
        messages = [{"role": "system", "content": self.system}, {"role": "user", "content": user_prompt(row)}]
        raw = await self.client.chat(messages, json_schema=self.schema, max_tokens=600, temperature=0.0, cache=False)
        return guard(row["sentences"], json.loads(raw), set(self.skill_ids))


# ---------------------------------------------------------------- the run
def load_rows() -> list[dict]:
    if not TEXTS.exists():
        raise SystemExit(f"{TEXTS.relative_to(ROOT)} is missing: run `python -m scripts.opportunities.jobs --texts-only` first.")
    return [json.loads(line) for line in TEXTS.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_progress() -> dict[str, dict]:
    done: dict[str, dict] = {}
    if PROGRESS.exists():
        for line in PROGRESS.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if "facts" in row:
                done[row["key"]] = row
    return done


def priority(rows: list[dict]) -> list[dict]:
    jobs = {j["id"]: j for j in json.loads(JOBS.read_text(encoding="utf-8"))["jobs"]}

    def rank(row: dict) -> tuple:
        j = jobs.get(row["id"], {})
        countries, remote = j.get("countries", []), j.get("remote")
        tier = (0 if "MY" in countries else 1 if "SG" in countries
                else 2 if remote == "WORLD" or (isinstance(remote, list) and "MY" in remote) else 3)
        return tier, -int((j.get("posted") or "0").replace("-", ""))

    return sorted(rows, key=rank)


def pending(rows: list[dict], done: dict[str, dict]) -> list[dict]:
    return [r for r in rows if r["sentences"] and done.get(r["key"], {}).get("h") != r["h"]]


def estimate(todo: list[dict], system_tokens: int) -> dict:
    prompt = sum(sum(len(s) + 6 for s in r["sentences"]) / 4 + 30 for r in todo)
    output = OUTPUT_TOKENS * len(todo)
    hours = (prompt / PREFILL_TOK_S + output / DECODE_TOK_S) / 3600 + (system_tokens / PREFILL_TOK_S / 3600 if todo else 0)
    return {"postings": len(todo), "prompt_tokens": int(prompt), "output_tokens": output, "hours": hours, "cost": hours * PRICE_PER_HOUR}


def write_facts(rows: list[dict], done: dict[str, dict], model: str) -> int:
    keys = {r["key"] for r in rows}
    facts = {k: v["facts"] for k, v in sorted(done.items()) if k in keys}
    OUT.write_text(json.dumps({"model": model, "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                               "read": len(facts), "facts": facts}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(facts)


def batch_client(concurrency: int) -> LLMClient:
    client = LLMClient(max_parallel=concurrency, cache_dir=None)
    client.timeout = 300                       # queued behind a full batch on the GPU
    return client


async def need_model(client: LLMClient) -> None:
    if not client.configured or not (await client.status()).get("online"):
        raise SystemExit("The model is not answering. Start the GPU first: python -m scripts.gpu start && python -m scripts.gpu wait")


async def run(limit: int | None, concurrency: int, client: LLMClient | None = None) -> dict:
    rows = load_rows()
    done = load_progress()
    todo = priority(pending(rows, done))[:limit] if limit else priority(pending(rows, done))
    client = client or batch_client(concurrency)
    await need_model(client)
    reader = Reader(client)
    print(f"Reading {len(todo)} postings with {client.model} ({concurrency} at a time); {len(done)} were read before.")
    queue: asyncio.Queue = asyncio.Queue()
    for row in todo:
        queue.put_nowait(row)
    stats = {"done": 0, "failed": 0, "dropped": 0, "chars": 0, "offline": False}
    started = time.time()
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    with PROGRESS.open("a", encoding="utf-8") as log:
        async def worker() -> None:
            while not queue.empty() and not stats["offline"]:
                row = queue.get_nowait()
                try:
                    facts, dropped = await reader.read(row)
                except LLMUnavailable as exc:
                    if not (await client.status(max_age=0)).get("online"):
                        stats["offline"] = True
                        return
                    stats["failed"] += 1
                    log.write(json.dumps({"key": row["key"], "h": row["h"], "error": str(exc)[:200]}) + "\n")
                    continue
                except (ValueError, KeyError, TypeError) as exc:
                    stats["failed"] += 1
                    log.write(json.dumps({"key": row["key"], "h": row["h"], "error": f"bad answer: {exc}"[:200]}) + "\n")
                    continue
                done[row["key"]] = {"key": row["key"], "h": row["h"], "facts": facts}
                log.write(json.dumps({**done[row["key"]], "dropped": dropped}, ensure_ascii=False) + "\n")
                log.flush()
                stats["done"] += 1
                stats["dropped"] += len(dropped)
                stats["chars"] += sum(len(s) for s in row["sentences"])
                if stats["done"] % 100 == 0:
                    rate = stats["done"] / (time.time() - started)
                    left = (len(todo) - stats["done"]) / rate / 3600 if rate else 0
                    print(f"  {stats['done']}/{len(todo)} · {rate * 60:.0f}/min · ≈{stats['chars'] / 4 / (time.time() - started):.0f} prompt tok/s"
                          f" · {left:.1f} h left (≈${left * PRICE_PER_HOUR:.2f})", flush=True)
                if stats["done"] % 500 == 0:
                    write_facts(rows, done, client.model)

        await asyncio.gather(*(worker() for _ in range(concurrency)))
    n = write_facts(rows, done, client.model)
    took = (time.time() - started) / 60
    print(f"Read {stats['done']} postings in {took:.1f} min ({stats['failed']} failed, {stats['dropped']} facts dropped by the guard). "
          f"{n} postings have facts in {OUT.relative_to(ROOT)}.")
    if stats["offline"]:
        print("The model went offline (GPU stopped?). Progress is saved: run the command again to continue.")
    return stats


# ---------------------------------------------------------------- accuracy on the gold set
def score(gold: list[dict], got: list[dict]) -> dict:
    tp = fp = fn = 0
    fields = {k: [0, 0] for k in ("years", "degree", "languages", "pay", "mode", "visa")}
    for g, facts in zip(gold, got):
        want, have = g["expect"], facts
        if g.get("skills") is not None:            # skills are labelled only where they are clear-cut
            ws = set(g["skills"].get("req", []) + g["skills"].get("nice", []))
            hs = set(have.get("req", []) + have.get("nice", []))
            tp, fp, fn = tp + len(ws & hs), fp + len(hs - ws), fn + len(ws - hs)
        for k in fields:
            a, b = want.get(k), have.get(k)
            if k == "languages":
                a, b = sorted(a or []), sorted(b or [])
            elif k == "degree":
                a, b = (a, want.get("degree_required")), (b, have.get("degree_required"))
            fields[k][0] += a == b
            fields[k][1] += 1
    out = {"skills_precision": tp / (tp + fp) if tp + fp else 1.0, "skills_recall": tp / (tp + fn) if tp + fn else 1.0}
    out.update({k: right / total for k, (right, total) in fields.items()})
    return out


async def evaluate(concurrency: int, client: LLMClient | None = None) -> dict:
    if not GOLD.exists():
        raise SystemExit(f"No gold set at {GOLD.relative_to(ROOT)}.")
    gold = json.loads(GOLD.read_text(encoding="utf-8"))
    client = client or batch_client(concurrency)
    await need_model(client)
    reader = Reader(client)

    async def read(g: dict) -> tuple[dict, list[str]]:
        try:
            return await reader.read(g)
        except (ValueError, KeyError, TypeError) as exc:      # a broken answer counts as reading nothing
            return {}, [f"bad answer: {exc}"[:80]]

    got = await asyncio.gather(*(read(g) for g in gold))
    result = score(gold, [facts for facts, _ in got])
    for g, (facts, dropped) in zip(gold, got):
        fields = {k: sorted(v) if k == "languages" else v for k, v in facts.items() if k not in ("req", "nice")}
        skills = {k: facts[k] for k in ("req", "nice") if k in facts}
        want_skills = {k: v for k, v in (g.get("skills") or {}).items() if v}
        if fields != g["expect"] or (g.get("skills") is not None and skills != want_skills):
            print(f"- {g['title'][:60]}\n    expected {json.dumps({**g['expect'], **want_skills}, ensure_ascii=False)}"
                  f"\n    got      {json.dumps(facts, ensure_ascii=False)}" + (f"\n    dropped  {dropped}" if dropped else ""))
    print("\n" + "  ".join(f"{k} {v:.0%}" for k, v in result.items()))
    return result


def pod_running() -> bool | None:
    """True/False from the RunPod API; None when it cannot say (no key, no network)."""
    try:
        from scripts import gpu
        env = gpu.read_env()
        return gpu.RunPod(env.get("RUNPOD_API_KEY", "")).pod(gpu.need_pod(env)).get("desiredStatus") == "RUNNING"
    except Exception:
        return None


def stop_gpu() -> None:
    try:
        from scripts import gpu
        env = gpu.read_env()
        gpu.stop(gpu.RunPod(env.get("RUNPOD_API_KEY", "")), env)
    except Exception as exc:          # the in-pod watchdog stops it after 20 idle minutes anyway
        print(f"Could not stop the GPU ({exc}); the watchdog will stop it after 20 idle minutes.")


def read_everything(limit: int | None, concurrency: int, retries: int, then_stop: bool) -> None:
    """The whole run: continues after a dropped connection while the pod still runs, and optionally stops the GPU."""
    outcome = "interrupted"
    try:
        for attempt in range(retries + 1):
            try:
                stats = asyncio.run(run(limit, concurrency))
            except SystemExit as exc:         # the model did not answer at the start
                print(exc)
                stats = {"offline": True}
            if not stats["offline"]:
                outcome = "finished"
                break
            running = pod_running()
            if running is False:
                print("The GPU pod is not running any more (stopped by the watchdog or by hand). Progress is saved.")
                break
            if attempt < retries:
                pause = min(60 * (attempt + 1), 300)       # proxy glitches (Cloudflare 520) can last a few minutes
                print(f"Lost the model while the pod still runs: trying again in {pause} s ({attempt + 1}/{retries}).", flush=True)
                time.sleep(pause)
        left = len(pending(load_rows(), load_progress()))
        print(f"{left} postings left to read.")
    finally:
        if then_stop:
            stop_gpu()
        print(f"PATHAI_ENRICH_END {outcome}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m scripts.opportunities.enrich")
    ap.add_argument("--dry-run", action="store_true", help="only show what is left to read and what it costs")
    ap.add_argument("--limit", type=int, help="read at most this many postings (a pilot)")
    ap.add_argument("--concurrency", type=int, default=32)
    ap.add_argument("--eval", action="store_true", help="accuracy on the gold set")
    ap.add_argument("--then-stop", action="store_true", help="switch the GPU pod off at the end (finished or not)")
    ap.add_argument("--retries", type=int, default=10, help="continue after a dropped connection while the pod still runs")
    args = ap.parse_args()
    if args.eval:
        asyncio.run(evaluate(min(args.concurrency, 16)))
        return
    if args.dry_run:
        rows = load_rows()
        todo = pending(rows, load_progress())
        todo = priority(todo)[: args.limit] if args.limit else todo
        e = estimate(todo, len(system_prompt(get_catalog())) // 4)
        print(f"{e['postings']} postings to read: ≈{e['prompt_tokens'] / 1e6:.1f}M prompt + {e['output_tokens'] / 1e6:.1f}M output tokens "
              f"≈ {e['hours']:.1f} GPU hours ≈ ${e['cost']:.2f} (estimate; the pilot measures the real speed)")
        return
    read_everything(args.limit, args.concurrency, args.retries, args.then_stop)


if __name__ == "__main__":
    main()
