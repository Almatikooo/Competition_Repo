"""The fact sheet behind the personal AI review and the career chat on the results page.

Everything the model may say about a person comes from here: their profile, how AI is changing their current job, and
their top options with fit, demand, hours to job-ready at their own pace, the first skills to learn, and the job
market for each option (from the postings the model read). The model writes words around these facts; the number
guard in app/llm/tasks.py rejects any number that is not in them.
"""
import math

from . import opportunities as opp
from .catalog import Catalog
from .engine.matching import Profile, Weights, current_role_outlook, rank_roles

TOP_OPTIONS = 3


def person_facts(catalog: Catalog, outlook: dict, profile: Profile, weights: Weights, scenario: str, country: str = "MY") -> dict:
    title = lambda rid: catalog.roles[rid]["title"]["en"]
    skill = lambda sid: catalog.skills[sid]["name"]["en"]
    hours = profile.hours_per_week
    options = []
    for r in rank_roles(catalog, outlook, profile, weights, scenario)[:TOP_OPTIONS]:
        gaps = sorted((i for i in r["items"] if i["status"] != "have" and i["gap_hours"]), key=lambda i: -i["weight"])[:3]
        market = opp.market_for(profile, [], country, r["id"])
        basis = market[market["basis"]] if market["basis"] != "none" else None
        option = {
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
