"""Path.AI API + static web app.   Run:  uvicorn app.main:app --app-dir src --reload"""
import asyncio
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .catalog import get_catalog
from .config import STATIC_DIR
from .engine.explain import build_facts, template_explanation
from .engine.forecast import Signals, compute_outlook, hn_sparkline, month_add, pct
from .engine.matching import Profile, Weights, current_role_outlook, match_role, rank_roles
from .engine.pathway import build_pathway
from .engine.profile import detect_skills, extract_text
from .learn import TEST_RULES, LearnError, get_learn, verify_certificate
from . import accounts, advisor
from . import opportunities as opp
from .llm import tasks
from .llm.client import ANSWERED_BY, LLMUnavailable, llm
from .signals.refresh import refresh as refresh_signals

app = FastAPI(title="Path.AI — career paths for the AI era", version="0.3.0")
app.include_router(accounts.router)      # optional sign-in with Google; guests need none


@app.middleware("http")
async def revalidate_assets(request, call_next):
    """ES modules import each other, so a stale cached i18n.js next to a fresh app.js shows raw keys.
    'no-cache' makes browsers revalidate every asset (cheap 304s via ETag) instead of guessing freshness."""
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache"
    return response


catalog = get_catalog()
learn = get_learn()
signals = Signals()
_outlooks: dict[str, dict] = {}
_refresh_state: dict = {"state": "idle", "log": []}
LANGS = {"en", "ms", "zh"}
EXPLAIN_TOP_N = 8


def resolve_as_of(as_of: str | None) -> str:
    options = signals.as_of_options()
    if not options:
        raise HTTPException(503, "No trend data yet. Run: PYTHONPATH=src python -m app.signals.refresh")
    return as_of if as_of in options else options[-1]


def outlook_for(as_of: str) -> dict:
    if as_of not in _outlooks:
        _outlooks[as_of] = compute_outlook(catalog, signals, as_of)
    return _outlooks[as_of]


def resolve_scenario(scenario: str) -> str:
    return scenario if scenario in catalog.scenarios else "moderate"


class Query(BaseModel):
    as_of: str | None = None
    scenario: str = "moderate"
    lang: str = "en"


class MatchQuery(Query):
    profile: Profile
    weights: Weights = Field(default_factory=Weights)


class RoleQuery(MatchQuery):
    role_id: str


class ReviewQuery(MatchQuery):
    country: str = Field(default="MY", pattern=r"^([A-Z]{2}|REMOTE)$")     # where the person looks for jobs


class ChatMessage(BaseModel):
    role: str = Field(pattern=r"^(user|assistant)$")
    content: str = Field(min_length=1, max_length=600)


class LearningProgress(BaseModel):
    done: int = Field(default=0, ge=0, le=1000)          # lessons done in this course
    chapters: int = Field(default=0, ge=0, le=100)       # chapter tests passed
    final: bool = False


class CoachContext(BaseModel):
    """What the person did on Path.AI, as their browser keeps it (nothing of it is stored on the server)."""
    learning: dict[Annotated[str, Field(max_length=40)], LearningProgress] = Field(default_factory=dict, max_length=60)
    certified: list[Annotated[str, Field(max_length=40)]] = Field(default_factory=list, max_length=60)
    plans: dict[Annotated[str, Field(max_length=60)], list[Annotated[str, Field(max_length=40)]]] = Field(default_factory=dict, max_length=8)


class ChatQuery(ReviewQuery):
    messages: list[ChatMessage] = Field(min_length=1, max_length=12)
    context: CoachContext = Field(default_factory=CoachContext)


class NextJobsQuery(BaseModel):
    profile: Profile
    certified: list[Annotated[str, Field(max_length=40)]] = Field(default_factory=list, max_length=60)
    country: str = Field(pattern=r"^([A-Z]{2}|REMOTE)$")
    roles: list[Annotated[str, Field(max_length=60)]] = Field(default_factory=list, max_length=8)
    level: str | None = Field(default=None, pattern=r"^(any|early|mid|senior)$")
    title: str = Field(default="", max_length=120)          # role title for job-site searches
    country_name: str = Field(default="", max_length=80)    # English country name for job-site searches
    lang: str = "en"


class NextWhyQuery(BaseModel):
    profile: Profile
    certified: list[Annotated[str, Field(max_length=40)]] = Field(default_factory=list, max_length=60)
    job_id: str = Field(pattern=r"^j\d{1,6}$")
    lang: str = "en"


class NextMarketQuery(BaseModel):
    profile: Profile
    certified: list[Annotated[str, Field(max_length=40)]] = Field(default_factory=list, max_length=60)
    country: str = Field(pattern=r"^([A-Z]{2}|REMOTE)$")
    role: str = Field(max_length=60)
    lang: str = "en"
    country_name: str = Field(default="", max_length=80)


class NextStudyQuery(BaseModel):
    country: str = Field(pattern=r"^[A-Z]{2}$")
    roles: list[Annotated[str, Field(max_length=60)]] = Field(default_factory=list, max_length=8)
    study_field: str | None = Field(default=None, max_length=40)


class TestStart(BaseModel):
    chapter: int | None = None  # 1-based chapter; leave out for the final test
    chapters: list[Annotated[str, Field(max_length=600)]] = Field(default_factory=list, max_length=30)  # signed chapter passes
    previous: str | None = Field(default=None, max_length=3000)  # the last attempt, so a retake asks different questions


class TestAnswers(BaseModel):
    attempt: str = Field(max_length=3000)
    answers: list[int | None] = Field(max_length=100)


class CertificateRequest(BaseModel):
    token: str = Field(max_length=600)  # the signed final-test pass
    name: str = Field(max_length=200)


# ---------------------------------------------------------------- metadata

@app.get("/api/meta")
async def meta() -> dict:
    hn_months = signals.months
    latest_thread = signals.hn["months"].get(hn_months[-1], {}) if hn_months else {}
    oa = signals.openalex.get("buckets", {})
    return {
        "as_of_options": signals.as_of_options(),
        "as_of_default": signals.latest(),
        "scenarios": list(catalog.scenarios.values()),
        "categories": catalog.skill_categories,
        "skills": [{"id": s["id"], "name": s["name"], "category": s["category"], "hours": s["hours"],
                    "has_market_signal": bool(s.get("hn")), "short": s.get("short"),
                    "related": catalog.related[s["id"]],
                    "sdgs": [{"goal": catalog.goal_of(x["target"]), **x} for x in s.get("sdgs", [])]} for s in catalog.skills.values()],
        "roles": [{"id": r["id"], "kind": r["kind"], "family": r["family"], "title": r["title"], "summary": r["summary"],
                   "tags": r["tags"], "taxonomy": r["taxonomy"], "skills": r["skills"],
                   "wef": catalog.claims[r["wef"]]["text"] if r.get("wef") else None, "wef_dir": r.get("wef_dir"),
                   "sdgs": [{"goal": catalog.goal_of(s["target"]), **s} for s in r["sdgs"]]}
                  for r in catalog.roles.values()],
        "sdg_goals": list(catalog.sdg_goals.values()),
        "sdg_targets": catalog.sdg_targets,
        "sdg_targets_local": catalog.sdg_targets_local,
        "interest_tags": catalog.interest_tags,
        "interest_tiles": catalog.interest_tiles,
        "study_fields": catalog.study_fields,
        "sources": catalog.sources,
        "model": catalog.model,
        "signals": {
            "hn": {"first_month": hn_months[0] if hn_months else None, "last_month": hn_months[-1] if hn_months else None,
                   "posts": sum(m["posts"] for m in signals.hn["months"].values()),
                   "latest_thread_url": latest_thread.get("url"), "fetched_at": latest_thread.get("fetched_at"),
                   "status": signals.meta.get("hn", {}).get("status")},
            "openalex": {"buckets": sorted(oa), "fetched_at": signals.openalex.get("refreshed_at"),
                         "status": signals.meta.get("openalex", {}).get("status")},
            "refreshed_at": max((signals.meta.get(k, {}).get("refreshed_at") or "" for k in ("hn", "openalex")), default="") or None,
        },
        "resources": {"count": len(catalog.resources), "checked": catalog.resources_checked},
        "llm": await llm.status(),
    }


@app.get("/api/personas")
def personas() -> dict:
    return {"personas": catalog.personas["personas"]}


# ---------------------------------------------------------------- 1. intake

@app.post("/api/profile/parse")
async def parse_profile(file: UploadFile | None = File(None), text: str = Form("")) -> dict:
    if file is not None and file.filename:
        try:
            text = extract_text(file.filename, await file.read())
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        except Exception:
            raise HTTPException(400, "Could not read this file. Try a text-based PDF or paste the text.")
    if not text.strip():
        raise HTTPException(400, "Upload a CV or paste some text.")
    found = {s["id"]: s for s in detect_skills(catalog, text)}
    engine, rejected, note = "rules", [], None
    if llm.configured:
        try:
            llm_skills, rejected = await tasks.extract_skills(catalog, text)
            for s in llm_skills:
                rule = found.get(s["id"])
                found[s["id"]] = {**s, "matched": rule["matched"] if rule else [], "source": "llm+rules" if rule else "llm"}
            engine = "llm"
        except (LLMUnavailable, ValueError, KeyError) as exc:
            note = f"Language model unavailable, used rule-based extraction ({exc})"[:200]
    return {"engine": engine, "skills": sorted(found.values(), key=lambda s: (-s["level"], s["id"])),
            "rejected_by_guardrail": len(rejected), "note": note, "chars": len(text)}


# ---------------------------------------------------------------- 2. radar

@app.post("/api/radar")
def radar(q: Query) -> dict:
    as_of, scenario = resolve_as_of(q.as_of), resolve_scenario(q.scenario)
    out = outlook_for(as_of)
    skills = []
    for sid, s in out["skills"].items():
        g, b = s["growth"][scenario], s["band"][scenario]
        market = s["market"] or {}
        skills.append({
            "id": sid, "category": catalog.skills[sid]["category"], "ring": s["ring"][scenario],
            "pct": pct(g), "low": pct(g - b), "high": pct(g + b), "confidence": s["confidence"],
            "by_scenario": {k: pct(v) for k, v in s["growth"].items()},
            "components": {"market": pct(s["components"]["market"]), "prior": pct(s["components"]["prior"]),
                           "ai": pct(catalog.scenarios[scenario]["pace"] * s["components"]["ai_base"])},
            "market": {k: market.get(k) for k in ("available", "mentions_recent", "mentions_base", "share_recent",
                                                   "share_base", "window_recent", "window_base")} if market else None,
            "drivers": s["drivers"][:3],
            "wef": catalog.claims[s["wef"]]["text"] if s["wef"] else None,
        })
    caps = out["capabilities"]
    return {"as_of": as_of, "scenario": scenario, "skills": skills,
            "capabilities": [{**c, "momentum_pct": pct(c["momentum"]) if c["available"] else None}
                             for c in caps["topics"].values()],
            "field": caps["field"], "bucket_recent": caps["bucket_recent"], "bucket_base": caps["bucket_base"]}


@app.get("/api/skill/{sid}")
def skill_detail(sid: str, as_of: str | None = None) -> dict:
    if sid not in catalog.skills:
        raise HTTPException(404, "unknown skill")
    as_of = resolve_as_of(as_of)
    s = outlook_for(as_of)["skills"][sid]
    return {"id": sid, "as_of": as_of,
            "sparkline": hn_sparkline(signals, "skills", sid, as_of) if catalog.skills[sid].get("hn") else [],
            "market": s["market"], "drivers": s["drivers"], "confidence": s["confidence"],
            "by_scenario": {k: {"pct": pct(v), "low": pct(v - s["band"][k]), "high": pct(v + s["band"][k])}
                            for k, v in s["growth"].items()},
            "resources": catalog.resources_for(sid), "sdgs": catalog.skills[sid]["sdgs"]}


# ---------------------------------------------------------------- 3. matching

@app.post("/api/match")
def match(q: MatchQuery) -> dict:
    as_of, scenario = resolve_as_of(q.as_of), resolve_scenario(q.scenario)
    lang = q.lang if q.lang in LANGS else "en"
    out = outlook_for(as_of)
    ranked = rank_roles(catalog, out, q.profile, q.weights, scenario)
    for r in ranked[:EXPLAIN_TOP_N]:
        facts = build_facts(catalog, signals, out, r, scenario, lang)
        r["explanation"] = template_explanation(facts, lang)
        r["sources"] = facts["sources"]
        # same number the plan page shows (includes missing prerequisites)
        r["plan_hours"] = build_pathway(catalog, out, q.profile, r["id"], scenario)["total_hours"]
    changes = None
    prev = month_add(as_of, -1)
    if prev in signals.as_of_options():
        prev_out = outlook_for(prev)
        prev_rank = {r["id"]: r["rank"] for r in rank_roles(catalog, prev_out, q.profile, q.weights, scenario)}
        relevant = set(q.profile.skills) | {i["id"] for r in ranked[:3] for i in r["items"] if i["status"] != "have"}
        skill_moves = sorted(
            ({"id": sid, "now": pct(out["skills"][sid]["growth"][scenario]),
              "prev": pct(prev_out["skills"][sid]["growth"][scenario])} for sid in relevant),
            key=lambda m: -abs(m["now"] - m["prev"]))
        changes = {"prev_as_of": prev,
                   "roles": [{"id": r["id"], "rank": r["rank"], "prev_rank": prev_rank[r["id"]]} for r in ranked[:EXPLAIN_TOP_N]],
                   "skills": [m for m in skill_moves[:3] if abs(m["now"] - m["prev"]) >= 0.1]}
    current = current_role_outlook(catalog, out, q.profile)
    if current:
        current["wef"] = catalog.claims[current["wef"]]["text"] if current["wef"] else None
        my = catalog.roles[current["id"]].get("wef_my")           # what employers in Malaysia expect for this job (WEF)
        current["wef_my"] = {"job": catalog.claims[my]["job"], "net_growth_pct": catalog.claims[my]["net_growth_pct"],
                             "link": catalog.claim_source(my)[1]} if my else None
    return {"as_of": as_of, "scenario": scenario, "roles": ranked, "current": current, "changes": changes}


@app.post("/api/explain")
async def explain(q: RoleQuery) -> dict:
    as_of, scenario = resolve_as_of(q.as_of), resolve_scenario(q.scenario)
    lang = q.lang if q.lang in LANGS else "en"
    if q.role_id not in catalog.roles:
        raise HTTPException(404, "unknown role")
    out = outlook_for(as_of)
    ranked = next((r for r in rank_roles(catalog, out, q.profile, q.weights, scenario) if r["id"] == q.role_id), None)
    if ranked is None:
        raise HTTPException(404, "role is not among this profile's future roles")
    facts = build_facts(catalog, signals, out, ranked, scenario, lang)
    result = {"engine": "template", "text": template_explanation(facts, lang), "sources": facts["sources"],
              "guardrail": None, "model": None}
    try:                                  # a saved answer is used even when no model is configured or the GPU is off
        text, problems = await tasks.explain(facts, lang)
        if problems:
            result["guardrail"] = {"rejected": True, "problems": problems, "draft": text}
        else:
            result.update(engine="llm", text=text, model=ANSWERED_BY.get() or llm.model, guardrail={"rejected": False})
    except (LLMUnavailable, ValueError, KeyError) as exc:
        result["guardrail"] = {"rejected": False, "error": str(exc)[:200]}
    return result


def _person_facts(q: ReviewQuery) -> tuple[dict, str]:
    facts = advisor.person_facts(catalog, outlook_for(resolve_as_of(q.as_of)), q.profile, q.weights, resolve_scenario(q.scenario), q.country)
    return facts, q.lang if q.lang in LANGS else "en"


@app.post("/api/review")
async def ai_review(q: ReviewQuery) -> dict:
    """The personal AI review on the results page: four sentences from the person's own facts (numbers checked)."""
    facts, lang = _person_facts(q)
    try:
        text, problems = await tasks.career_review(facts, lang)
    except (LLMUnavailable, ValueError, KeyError) as exc:
        return {"engine": None, "text": None, "error": str(exc)[:200]}
    if problems:
        return {"engine": None, "text": None, "guardrail": {"rejected": True, "problems": problems}}
    return {"engine": "llm", "text": text, "model": ANSWERED_BY.get() or llm.model}


@app.post("/api/chat")
async def career_chat(q: ChatQuery) -> dict:
    """The career coach: answers about the person's own career from their facts only (numbers and links checked)."""
    if q.messages[-1].role != "user":
        raise HTTPException(422, "the last message must be the person's question")
    ctx = q.context
    facts = advisor.coach_facts(catalog, learn, outlook_for(resolve_as_of(q.as_of)), q.profile, q.weights, resolve_scenario(q.scenario),
                                q.country, ctx.learning, ctx.certified, ctx.plans)
    lang = q.lang if q.lang in LANGS else "en"
    try:
        text, problems, link_ids = await tasks.career_chat(facts, [m.model_dump() for m in q.messages], lang)
    except (LLMUnavailable, ValueError, KeyError) as exc:
        return {"engine": None, "text": None, "error": str(exc)[:200]}
    if problems:
        return {"engine": None, "text": None, "guardrail": {"rejected": True, "problems": problems}}
    return {"engine": "llm", "text": text, "links": [_coach_link(x, q.country) for x in link_ids], "model": ANSWERED_BY.get() or llm.model}


def _coach_link(link_id: str, country: str) -> dict:
    """A link the coach chose, as the page shows it (labels are written in the page's language)."""
    kind, _, ref = link_id.partition(":")
    if kind == "job" and (job := opp.job_by_id(ref)):
        return {"kind": "job", "id": ref, "title": job["title"], "company": job["company"], "url": job["url"]}
    return {"kind": kind, "id": ref or None, "country": country if kind == "jobs" else None}


# ---------------------------------------------------------------- 4. pathway

@app.post("/api/pathway")
def pathway(q: RoleQuery) -> dict:
    if q.role_id not in catalog.roles or catalog.roles[q.role_id]["kind"] != "target":
        raise HTTPException(404, "unknown role")
    as_of, scenario = resolve_as_of(q.as_of), resolve_scenario(q.scenario)
    return {"as_of": as_of, "scenario": scenario,
            **build_pathway(catalog, outlook_for(as_of), q.profile, q.role_id, scenario)}


# ---------------------------------------------------------------- HR / L&D view

@app.post("/api/team")
def team(q: Query) -> dict:
    as_of, scenario = resolve_as_of(q.as_of), resolve_scenario(q.scenario)
    out = outlook_for(as_of)
    data = catalog.personas["team"]
    targets = data["target_roles"]
    members, gap_count = [], {}
    for m in data["members"]:
        profile = Profile(skills=m["skills"], current_role=m["current_role"])
        fits = {rid: match_role(catalog, profile, rid) for rid in targets}
        best = max(targets, key=lambda rid: fits[rid]["fit"])
        for item in fits[best]["items"]:
            if item["status"] != "have":
                gap_count[item["id"]] = gap_count.get(item["id"], 0) + 1
        cur = out["roles"][m["current_role"]]["growth"][scenario]
        members.append({"id": m["id"], "alias": m["alias"], "current_role": m["current_role"],
                        "current_outlook_pct": pct(cur), "fits": {rid: round(f["fit"] * 100) for rid, f in fits.items()},
                        "best": best, "best_gap_hours": fits[best]["gap_hours"]})
    heat = sorted(({"skill": sid, "members": n, "outlook_pct": pct(out["skills"][sid]["growth"][scenario])}
                   for sid, n in gap_count.items()), key=lambda x: -x["members"])
    return {"as_of": as_of, "scenario": scenario, "name": data["name"], "targets": targets,
            "target_outlook": {rid: pct(out["roles"][rid]["growth"][scenario]) for rid in targets},
            "members": members, "skill_gaps": heat}


# ---------------------------------------------------------------- Learn & certificates

def course_or_404(sid: str) -> None:
    if sid not in learn.courses:
        raise HTTPException(404, "unknown course")


@app.get("/api/learn/courses")
def learn_courses() -> dict:
    return {"courses": [learn.summary(sid) for sid in catalog.skills if sid in learn.courses], "tests": TEST_RULES}


@app.get("/api/learn/course/{sid}")
def learn_course(sid: str) -> dict:
    course_or_404(sid)
    return learn.detail(sid)


@app.get("/api/learn/course/{sid}/lesson/{lid}")
def learn_lesson(sid: str, lid: str) -> dict:
    course_or_404(sid)
    try:
        return learn.lesson(sid, lid)
    except KeyError:
        raise HTTPException(404, "unknown lesson")


@app.post("/api/learn/course/{sid}/test")
def learn_test(sid: str, body: TestStart) -> dict:
    course_or_404(sid)
    try:
        return learn.start_test(sid, body.chapter, body.chapters, body.previous)
    except LearnError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/learn/course/{sid}/test/grade")
def learn_test_grade(sid: str, body: TestAnswers) -> dict:
    course_or_404(sid)
    try:
        return learn.grade_test(sid, body.attempt, body.answers)
    except LearnError as exc:
        raise HTTPException(400, str(exc))


@app.post("/api/learn/course/{sid}/certificate")
def learn_certificate(sid: str, body: CertificateRequest) -> dict:
    course_or_404(sid)
    try:
        return {"certificate": learn.certificate(sid, body.token, body.name)}
    except LearnError as exc:
        raise HTTPException(400, str(exc))


# ---------------------------------------------------------------- Opportunities: jobs & universities

@app.get("/api/next/meta")
def next_meta() -> dict:
    return opp.meta()


@app.post("/api/next/jobs")
async def next_jobs(q: NextJobsQuery) -> dict:
    result = opp.jobs_for(q.profile, q.certified, q.country, q.roles, q.level)
    if result["scored"] and llm.saved_count() and not (await llm.status()).get("online"):
        lang = q.lang if q.lang in LANGS else "en"
        for item in result["local"][:12] + result["remote"][:12]:    # GPU off: is the AI's take on it saved?
            facts = opp.advice_facts(q.profile, q.certified, opp.job_by_id(item["id"]))
            item["advice_saved"] = llm.cached(tasks.advice_payload(facts, lang)) is not None
    first = next((r for r in q.roles if r in catalog.roles), None)
    title = q.title or (opp.search_title(first) if first else "")
    result["portals"] = opp.job_portals(q.country, title, q.country_name or q.country) if title else []
    result["search_title"] = title
    return result


@app.post("/api/next/why")
async def next_why(q: NextWhyQuery) -> dict:
    """The model's short take on one posting for this person, from its facts only (numbers checked)."""
    job = opp.job_by_id(q.job_id)
    if job is None:
        raise HTTPException(404, "unknown job")
    facts = opp.advice_facts(q.profile, q.certified, job)
    try:
        text, problems = await tasks.job_advice(facts, q.lang if q.lang in LANGS else "en")
    except (LLMUnavailable, ValueError, KeyError) as exc:
        return {"engine": None, "text": None, "error": str(exc)[:200]}
    if problems:
        return {"engine": None, "text": None, "guardrail": {"rejected": True, "problems": problems}}
    return {"engine": "llm", "text": text, "model": ANSWERED_BY.get() or llm.model}


def _market(q: NextMarketQuery) -> dict:
    if q.role not in catalog.roles:
        raise HTTPException(404, "unknown role")
    market = opp.market_for(q.profile, q.certified, q.country, q.role)
    growth = outlook_for(resolve_as_of(None))["roles"].get(q.role, {}).get("growth", {}).get("moderate")
    market["outlook_pct"] = pct(growth) if growth is not None else None
    return market


@app.post("/api/next/market")
async def next_market(q: NextMarketQuery) -> dict:
    """What postings for one direction ask for where the person wants to work, and how much of it they cover."""
    market = _market(q)
    if market["basis"] != "none" and llm.saved_count() and not (await llm.status()).get("online"):   # GPU off: saved?
        facts = opp.market_facts(market, market["outlook_pct"], q.country_name)
        market["ai_saved"] = llm.cached(tasks.market_payload(facts, q.lang if q.lang in LANGS else "en")) is not None
    return market


@app.post("/api/next/market/ai")
async def next_market_ai(q: NextMarketQuery) -> dict:
    """The model's short market check for this person, from the market statistics only (numbers checked)."""
    market = _market(q)
    if market["basis"] == "none":
        return {"engine": None, "text": None, "error": "too few postings for this direction"}
    facts = opp.market_facts(market, market["outlook_pct"], q.country_name)
    try:
        text, problems = await tasks.market_check(facts, q.lang if q.lang in LANGS else "en")
    except (LLMUnavailable, ValueError, KeyError) as exc:
        return {"engine": None, "text": None, "error": str(exc)[:200]}
    if problems:
        return {"engine": None, "text": None, "guardrail": {"rejected": True, "problems": problems}}
    return {"engine": "llm", "text": text, "model": ANSWERED_BY.get() or llm.model}


@app.post("/api/next/study")
def next_study(q: NextStudyQuery) -> dict:
    try:
        return opp.study_for(q.country, q.roles, q.study_field)
    except opp.OppError as exc:
        raise HTTPException(404, str(exc))


@app.get("/api/certificates/verify/{token}")
def certificate_verify(token: str) -> dict:
    return verify_certificate(token[:600])


# ---------------------------------------------------------------- live signal refresh

@app.post("/api/signals/refresh")
async def start_refresh() -> dict:
    if _refresh_state["state"] == "running":
        return _refresh_state

    async def job() -> None:
        _refresh_state.update(state="running", log=[], result=None, change=None, error=None)
        try:
            meta_after = await refresh_signals(log=lambda line: _refresh_state["log"].append(line))
            signals.reload()
            _outlooks.clear()
            _refresh_state.update(state="done", result={k: meta_after[k].get("status") for k in ("hn", "openalex") if k in meta_after},
                                  change=meta_after.get("change"))
        except Exception as exc:
            _refresh_state.update(state="error", error=str(exc)[:300])

    asyncio.create_task(job())
    return {"state": "running", "log": []}


@app.get("/api/signals/status")
def refresh_status() -> dict:
    return {**_refresh_state, "as_of_default": signals.latest()}


# ---------------------------------------------------------------- web app

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
