"""The jobs the language model does in the app, each behind a guardrail that rejects invented content.

1. extract_skills  — CV text -> skills from OUR taxonomy (enum-constrained ids) with a verbatim evidence quote.
                     Guard: the quote must literally occur in the CV, otherwise the skill is dropped.
2. explain         — fact sheet -> short explanation in EN / BM / ZH, citing [S1]..[Sn].
                     Guard: only citations that exist, and every number must appear in the fact sheet;
                     otherwise the deterministic template is used.
The model never chooses jobs, courses or statistics: those come from the catalog and the scoring engine.
"""
import json
import re

from ..catalog import Catalog
from .client import LLMUnavailable, llm

LANG_NAMES = {"en": "English", "ms": "Bahasa Malaysia", "zh": "Simplified Chinese"}
NUMBER = re.compile(r"(?<![\d.,])[-+]?\d+(?:[.,]\d+)*")   # "RM4,500" -> 4,500; "1,234,567" whole
CITATION = re.compile(r"\[(S\d+)\]")


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _number(raw: str) -> str:
    n = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", raw.lstrip("+-"))     # 4,500 -> 4500 (thousands)
    n = n.replace(",", ".")                                            # 3,5 -> 3.5 (decimal comma)
    if "." in n:
        n = n.rstrip("0").rstrip(".")                                  # 3.50 -> 3.5, 4.0 -> 4
    return n or "0"


def numbers_in(text: str) -> set[str]:
    return {_number(n) for n in NUMBER.findall(text)}


def guard_skills(catalog: Catalog, cv_text: str, items: list[dict]) -> tuple[list[dict], list[dict]]:
    cv = _norm(cv_text)
    kept, rejected = {}, []
    for item in items:
        sid, quote = item.get("id"), _norm(str(item.get("evidence", "")))
        if sid not in catalog.skills:
            rejected.append({**item, "reason": "unknown skill id"})
        elif len(quote) < 3 or quote not in cv:
            rejected.append({**item, "reason": "evidence not found in CV"})
        elif sid not in kept or item["level"] > kept[sid]["level"]:
            kept[sid] = {"id": sid, "level": int(item["level"]), "evidence": [item["evidence"]], "source": "llm"}
    return list(kept.values()), rejected


async def extract_skills(catalog: Catalog, cv_text: str) -> tuple[list[dict], list[dict]]:
    ids = sorted(catalog.skills)
    schema = {
        "type": "object", "additionalProperties": False, "required": ["skills"],
        "properties": {"skills": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["id", "level", "evidence"],
            "properties": {"id": {"type": "string", "enum": ids},
                           "level": {"type": "integer", "enum": [1, 2, 3]},
                           "evidence": {"type": "string"}}}}},
    }
    taxonomy = "\n".join(f"- {sid}: {catalog.skills[sid]['name']['en']}" for sid in ids)
    messages = [
        {"role": "system", "content": (
            "You map a CV onto a fixed skills taxonomy. Use only ids from the taxonomy. "
            "For each skill give a level (1 basic, 2 working, 3 advanced) and an evidence string that is an EXACT, "
            "verbatim quote copied from the CV. If there is no explicit evidence, leave the skill out. "
            "The CV may be in English, Bahasa Malaysia or Chinese.")},
        {"role": "user", "content": f"Taxonomy:\n{taxonomy}\n\nCV:\n<<<\n{cv_text[:12000]}\n>>>"},
    ]
    raw = await llm.chat(messages, json_schema=schema, max_tokens=900, temperature=0.0)
    items = json.loads(raw).get("skills", [])
    return guard_skills(catalog, cv_text, items)


def guard_explanation(text: str, facts: dict) -> list[str]:
    problems = []
    allowed_ids = {s["id"] for s in facts["sources"]}
    cited = set(CITATION.findall(text))
    if not cited:
        problems.append("no citations")
    if cited - allowed_ids:
        problems.append(f"unknown citations {sorted(cited - allowed_ids)}")
    allowed_numbers = numbers_in(json.dumps(facts, ensure_ascii=False))
    stray = numbers_in(CITATION.sub("", text)) - allowed_numbers
    if stray:
        problems.append(f"numbers not in facts {sorted(stray)}")
    return problems


async def explain(facts: dict, lang: str) -> tuple[str, list[str]]:
    schema = {"type": "object", "additionalProperties": False, "required": ["explanation"],
              "properties": {"explanation": {"type": "string"}}}
    public = {k: v for k, v in facts.items() if k != "citations"}
    messages = [
        {"role": "system", "content": (
            "You are a careful career-guidance assistant for Malaysian workers. Explain ONE recommendation in "
            f"{LANG_NAMES.get(lang, 'English')}, in 3-4 short sentences, warm and plain. Use ONLY the facts provided. "
            "Do not add any number that is not in the facts. Cite sources inline exactly like [S1] using the ids "
            "in 'sources'. End by reminding the person that this is an estimate and the decision is theirs.")},
        {"role": "user", "content": json.dumps(public, ensure_ascii=False)},
    ]
    def grounded(raw: str) -> bool:
        return not guard_explanation(json.loads(raw)["explanation"].strip(), facts)

    raw = await llm.chat(messages, json_schema=schema, max_tokens=450, temperature=0.3, accept=grounded)
    text = json.loads(raw)["explanation"].strip()
    return text, guard_explanation(text, facts)


def guard_numbers(text: str, facts: dict) -> list[str]:
    stray = numbers_in(text) - numbers_in(json.dumps(facts, ensure_ascii=False))
    return [f"numbers not in facts {sorted(stray)}"] if stray else []


ADVICE_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["advice"], "properties": {"advice": {"type": "string"}}}
ADVICE_PARAMS = {"max_tokens": 220, "temperature": 0.3}


def advice_messages(facts: dict, lang: str) -> list[dict]:
    return [
        {"role": "system", "content": (
            f"You are a careful, warm career adviser for Malaysian workers. In {LANG_NAMES.get(lang, 'English')}, in 2 or 3 "
            "short sentences, tell the person whether this job posting is a realistic next step for them, and the single "
            "most useful thing to do before applying. Use ONLY the facts provided and do not add any number that is not in "
            "them. If the posting asks for more years of experience or a language the person does not list, say so plainly. "
            "Do not repeat the job title. Plain text, no lists.")},
        {"role": "user", "content": json.dumps(facts, ensure_ascii=False)},
    ]


def advice_payload(facts: dict, lang: str) -> dict:
    """The exact request job_advice sends: used to tell whether a saved answer exists while the GPU is off."""
    return llm.payload(advice_messages(facts, lang), json_schema=ADVICE_SCHEMA, **ADVICE_PARAMS)


async def job_advice(facts: dict, lang: str) -> tuple[str, list[str]]:
    """2-3 sentences on whether one job posting is a realistic next step, from a fact sheet only."""
    def grounded(raw: str) -> bool:
        return not guard_numbers(json.loads(raw)["advice"].strip(), facts)

    raw = await llm.chat(advice_messages(facts, lang), json_schema=ADVICE_SCHEMA, accept=grounded, **ADVICE_PARAMS)
    text = json.loads(raw)["advice"].strip()
    return text, guard_numbers(text, facts)


CHECK_SCHEMA = {"type": "object", "additionalProperties": False, "required": ["check"], "properties": {"check": {"type": "string"}}}
CHECK_PARAMS = {"max_tokens": 260, "temperature": 0.3}


def market_messages(facts: dict, lang: str) -> list[dict]:
    return [
        {"role": "system", "content": (
            f"You are a careful, warm career adviser for Malaysian workers. In {LANG_NAMES.get(lang, 'English')}, in 3 or 4 "
            "short sentences, compare the person with what employers in this job market ask for: how much of that demand "
            "they already cover, what most stands between them and these jobs, and one concrete next step. Use ONLY the "
            "facts provided and do not add any number that is not in them. If the figures are for the direction worldwide "
            "because there are few postings in that place, say so. Plain text, no lists.")},
        {"role": "user", "content": json.dumps(facts, ensure_ascii=False)},
    ]


def market_payload(facts: dict, lang: str) -> dict:
    return llm.payload(market_messages(facts, lang), json_schema=CHECK_SCHEMA, **CHECK_PARAMS)


async def market_check(facts: dict, lang: str) -> tuple[str, list[str]]:
    """3-4 sentences comparing the person with the job market for one direction, from its statistics only."""
    def grounded(raw: str) -> bool:
        return not guard_numbers(json.loads(raw)["check"].strip(), facts)

    raw = await llm.chat(market_messages(facts, lang), json_schema=CHECK_SCHEMA, accept=grounded, **CHECK_PARAMS)
    text = json.loads(raw)["check"].strip()
    return text, guard_numbers(text, facts)


__all__ = ["extract_skills", "explain", "job_advice", "market_check", "guard_skills", "guard_explanation", "guard_numbers", "LLMUnavailable"]
