"""Checks the language model end to end through Path.AI's own API, on the six example people (GPU on):

    python -m scripts.ai_check           # CV reading and explanations in EN / MS / ZH: accepted by the guardrails? how fast?
    python -m scripts.ai_check --save    # also save the accepted answers to data/ai/answers.jsonl (committed), so the
                                         # demo shows real model answers for the example people with the GPU off

CV reading: the skills the model adds (each with a verbatim quote) against the person's profile, and how many the
evidence guard rejected. Explanations: for each person's top role, whether the citation-and-number guard accepted
the model's text or fell back to the template.
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402
from app.catalog import get_catalog  # noqa: E402
from app.llm.client import llm  # noqa: E402
from app.main import app  # noqa: E402

LANGS = ("en", "ms", "zh")


def record_keys() -> list[str]:
    """Wraps the shared client so every request's cache key is noted (to save exactly the answers this check used)."""
    keys: list[str] = []
    original = llm.chat

    async def chat(messages, **kw):
        keys.append(llm._key(llm.payload(messages, **{k: v for k, v in kw.items() if k in ("json_schema", "max_tokens", "temperature")})))
        return await original(messages, **kw)

    llm.chat = chat
    return keys


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m scripts.ai_check")
    ap.add_argument("--save", action="store_true", help="save the accepted answers for the demo")
    ap.add_argument("--people", type=int, default=6)
    args = ap.parse_args()
    keys = record_keys()
    client, catalog = TestClient(app), get_catalog()
    status = client.get("/api/meta").json()["llm"]
    if not status.get("online"):
        raise SystemExit("The model is not answering: python -m scripts.gpu start && python -m scripts.gpu wait")
    print(f"Model: {status['model']}\n")
    accepted = total = 0
    for person in catalog.personas["personas"][: args.people]:
        t = time.time()
        cv = client.post("/api/profile/parse", data={"text": person["cv_text"]}).json()
        by_model = {s["id"] for s in cv["skills"] if s.get("source", "").startswith("llm")}
        real = set(person["skills"])
        print(f"{person['name']}: CV via {cv['engine']} in {time.time() - t:.1f}s · model added {sorted(by_model - real) or 'nothing new'}"
              f" · found {len(by_model & real)}/{len(real)} of the profile skills · guard rejected {cv['rejected_by_guardrail']}")
        profile = {k: person[k] for k in ("skills", "interests", "sdg_priorities", "current_role", "hours_per_week")}
        top = client.post("/api/match", json={"profile": profile}).json()["roles"][0]["id"]
        for lang in LANGS:
            t = time.time()
            r = client.post("/api/explain", json={"profile": profile, "role_id": top, "lang": lang}).json()
            ok = r["engine"] == "llm"
            accepted, total = accepted + ok, total + 1
            note = "" if ok else f" · {r.get('guardrail')}"
            print(f"   {top} [{lang}] {'model text accepted' if ok else 'template (guard)'} in {time.time() - t:.1f}s{note}")
            if ok and lang == "en":
                print(f"      “{r['text'][:220]}…”")
    print(f"\nExplanations accepted by the guard: {accepted}/{total}")
    if args.save:
        answers = llm._load_answers()
        rows = [{"k": k, "v": answers[k], "model": llm.model} for k in dict.fromkeys(keys) if k in answers]
        config.LLM_SAVED_ANSWERS.parent.mkdir(parents=True, exist_ok=True)
        old = {json.loads(line)["k"]: line for line in config.LLM_SAVED_ANSWERS.read_text(encoding="utf-8").splitlines()} \
            if config.LLM_SAVED_ANSWERS.exists() else {}
        old.update({r["k"]: json.dumps(r, ensure_ascii=False) for r in rows})
        config.LLM_SAVED_ANSWERS.write_text("\n".join(old.values()) + "\n", encoding="utf-8")
        print(f"Saved {len(rows)} answers to {config.LLM_SAVED_ANSWERS.relative_to(ROOT)} ({len(old)} in all).")


if __name__ == "__main__":
    main()
