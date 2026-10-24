"""The fact sheets behind the personal AI review on the results page and the career coach.

Everything the model may say about a person comes from here: their profile, how AI is changing their current job, and
their top options with fit, demand, hours to job-ready at their own pace, the first skills to learn, and the job
market for each option (from the postings the model read). The model writes words around these facts; the number
guard in app/llm/tasks.py rejects any number that is not in them.
"""
import math

from . import opportunities as opp
from .catalog import Catalog
from .engine.matching import Profile, Weights, current_role_outlook, rank_roles
from .engine.pathway import build_pathway

TOP_OPTIONS = 3
COACH_OPTIONS = 5
COACH_JOBS = 5


def person_facts(catalog: Catalog, outlook: dict, profile: Profile, weights: Weights, scenario: str, country: str = "MY",
                 top: int = TOP_OPTIONS) -> dict:
    title = lambda rid: catalog.roles[rid]["title"]["en"]
    skill = lambda sid: catalog.skills[sid]["name"]["en"]
    hours = profile.hours_per_week
    options = []
    for rank, r in enumerate(rank_roles(catalog, outlook, profile, weights, scenario)[:top], start=1):
        gaps = sorted((i for i in r["items"] if i["status"] != "have" and i["gap_hours"]), key=lambda i: -i["weight"])[:3]
        market = opp.market_for(profile, [], country, r["id"])
        basis = market[market["basis"]] if market["basis"] != "none" else None
        option = {
            "rank_on_their_results_page": rank,          # 1 = the best match the page shows first
            "option": title(r["id"]),
            "fit_percent": r["fit"],
            "demand_growth_percent_per_year": round(r["outlook"][scenario]["pct"]),
            "holds_up_in_every_ai_scenario": r["robust"],
            "hours_to_job_ready": r["gap_hours"],
            "weeks_at_their_pace": math.ceil(r["gap_hours"] / hours) if hours and r["gap_hours"] else 0,
            "skills_to_learn_first": [{"skill": skill(i["id"]), "hours": i["gap_hours"]} for i in gaps],
            "open_postings_where_they_look": market["here"]["n"],
            "open_postings_worldwide": market["world"]["n"],
        }
        if basis and basis["coverage"] is not None:
            option["share_of_most_required_skills_they_have_percent"] = round(100 * basis["coverage"])
        options.append(option)
    person: dict = {"hours_per_week_for_learning": hours,
                    "skills_they_have": [skill(s) for s, level in sorted(profile.skills.items(), key=lambda kv: -kv[1]) if level >= 2][:8]}
    if profile.current_role in catalog.roles:
        person["current_job"] = title(profile.current_role)
        current = current_role_outlook(catalog, outlook, profile)
        if current:
            person["current_job_demand_growth_percent_per_year"] = round(current["outlook"][scenario]["pct"])
    if profile.years_experience is not None:
        person["years_of_experience"] = profile.years_experience
    if profile.languages:
        person["languages"] = [opp.LANGUAGE_NAMES.get(c, c) for c in profile.languages]
    where = "remote jobs open worldwide" if country == opp.REMOTE else country
    return {"person": person, "top_options": options, "where_they_look_for_jobs": where,
            "ai_pace_scenario": {"slow": "AI changes work slower than expected", "moderate": "AI changes work as expected",
                                 "fast": "AI changes work faster than expected"}.get(scenario, scenario)}


def coach_facts(catalog: Catalog, learn, outlook: dict, profile: Profile, weights: Weights, scenario: str, country: str,
                learning: dict, certified: list[str], plans: dict[str, list[str]]) -> dict:
    """Everything the career coach may say about this person: the review's facts for their top five options, what
    employers in Malaysia expect for their current job, their courses and plans (sent by their browser), open jobs
    where they look, and the Path.AI pages the coach may link to (`links_you_can_offer`, the only allowed link ids)."""
    facts = person_facts(catalog, outlook, profile, weights, scenario, country, top=COACH_OPTIONS)
    skill = lambda sid: catalog.skills[sid]["name"]["en"]
    title = lambda rid: catalog.roles[rid]["title"]["en"]
    links: dict[str, str] = {}
    ranked = [r["id"] for r in rank_roles(catalog, outlook, profile, weights, scenario)[:COACH_OPTIONS]]
    for rid in ranked:
        links[f"plan:{rid}"] = f"their learning plan for {title(rid)}"
    wef = catalog.roles.get(profile.current_role or "", {}).get("wef_my")
    if wef:
        claim = catalog.claims[wef]
        facts["person"]["current_job_outlook_from_employers_in_malaysia"] = {
            "job_group": claim["job"], "net_change_percent_by_2030": claim["net_growth_pct"], "source": "World Economic Forum, Future of Jobs Report 2025"}
    courses = []
    for sid, p in learning.items():
        course = learn.courses.get(sid)
        if not course or not (p.done or p.chapters or p.final or sid in certified):
            continue
        courses.append({"course": skill(sid), "lessons_done": min(p.done, len(course["lessons"])), "lessons_total": len(course["lessons"]),
                        "chapter_tests_passed": min(p.chapters, len(course["modules"])), "chapters": len(course["modules"]),
                        "certificate": sid in certified})
        links[f"course:{sid}"] = f"their {skill(sid)} course"
    for sid in certified:
        if sid in learn.courses and f"course:{sid}" not in links:
            courses.append({"course": skill(sid), "certificate": True})
            links[f"course:{sid}"] = f"their {skill(sid)} course"
    if courses:
        facts["their_courses"] = sorted(courses, key=lambda c: (-c["certificate"], -c.get("lessons_done", 0)))[:8]
    your_plans = []
    for rid, done in list(plans.items())[:3]:
        if rid not in catalog.roles or catalog.roles[rid]["kind"] != "target":
            continue
        steps = build_pathway(catalog, outlook, profile, rid, scenario)["steps"]
        ticked = set(done) | set(certified)
        left = [st for st in steps if st["skill"] not in ticked]
        your_plans.append({"role": title(rid), "steps_done": len(steps) - len(left), "steps_total": len(steps),
                           "hours_left": sum(st["hours"] for st in left),
                           "next_steps": [{"skill": skill(st["skill"]), "hours": st["hours"]} for st in left[:2]]})
        links[f"plan:{rid}"] = f"their learning plan for {title(rid)}"
    if your_plans:
        facts["their_plans"] = your_plans
    for option in facts["top_options"][:3]:
        for item in option["skills_to_learn_first"][:2]:
            sid = next((k for k, v in catalog.skills.items() if v["name"]["en"] == item["skill"]), None)
            if sid and sid in learn.courses:
                links.setdefault(f"course:{sid}", f"the free {item['skill']} course")
    found = opp.jobs_for(profile, certified, country, ranked[:3], limit=COACH_JOBS)
    jobs = (found["local"] or found["remote"])[:COACH_JOBS]
    if jobs:
        facts["open_jobs_where_they_look"] = [
            {"id": f"job:{j['id']}", "title": j["title"], "company": j["company"], "fit_percent": j["fit"], "level": j["level"],
             "posted": j["posted"], "they_lack": [skill(m["id"]) for m in j.get("missing", [])[:3]]} for j in jobs]
        links["jobs"] = "open jobs where they look"
        for j in jobs:
            links[f"job:{j['id']}"] = f"the {j['title']} posting at {j['company']}"
    links["learn"] = "all free Path.AI courses"
    facts["links_you_can_offer"] = links
    return facts
