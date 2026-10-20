"""The only two jobs the language model does, each behind a guardrail that rejects invented content.

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
NUMBER = re.compile(r"(?<![\w.])[-+]?\d+(?:[.,]\d+)?")
CITATION = re.compile(r"\[(S\d+)\]")


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def numbers_in(text: str) -> set[str]:
    return {n.replace(",", ".").lstrip("+-").rstrip("0").rstrip(".") or "0" for n in NUMBER.findall(text)}


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
    raw = await llm.chat(messages, json_schema=schema, max_tokens=450, temperature=0.3)
    text = json.loads(raw)["explanation"].strip()
    return text, guard_explanation(text, facts)


__all__ = ["extract_skills", "explain", "guard_skills", "guard_explanation", "LLMUnavailable"]
