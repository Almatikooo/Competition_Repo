"""Personalised reskilling pathway: ordered gap skills (prerequisites first, then core before supporting,
quick wins first), each with catalogued free / low-cost resources, a practice project, a time estimate
and SDG links. If no catalogued resource exists, the step says so instead of inventing one."""
import math
from collections import defaultdict

from ..catalog import Catalog
from .forecast import pct
from .matching import Profile, gap_hours, match_role, skill_credit

COST_RANK = {"free": 0, "free_audit": 1, "low_cost": 2, "fee": 3}
MIN_STEP_HOURS = 4


def pick_resources(catalog: Catalog, sid: str, current_level: int, hours_needed: int) -> dict:
    candidates = catalog.resources_for(sid)
    courses = [r for r in candidates if r["kind"] != "credential"]
    credentials = [r for r in candidates if r["kind"] == "credential"]
    want = "beginner" if current_level == 0 else "intermediate"
    courses.sort(key=lambda r: (r["level"] != want, COST_RANK[r["cost"]], abs(r["hours"] - hours_needed)))
    credentials.sort(key=lambda r: (COST_RANK[r["cost"]], r["hours"]))
    return {"primary": courses[0] if courses else None, "alternatives": courses[1:3],
            "credential": credentials[0] if credentials else None}


def build_pathway(catalog: Catalog, outlook: dict, profile: Profile, rid: str, scenario: str) -> dict:
    role = catalog.roles[rid]
    match = match_role(catalog, profile, rid)
    needed = {i["id"]: dict(i) for i in match["items"] if i["status"] != "have"}
    stack = list(needed)
    while stack:  # pull in missing prerequisites
        for pre in catalog.skills[stack.pop()]["prereqs"]:
            if pre not in needed and profile.skills.get(pre, 0) < 1:
                credit = skill_credit(catalog, profile.skills, pre, 1)
                needed[pre] = {"id": pre, "weight": 0.5, "required_level": 1, **credit, "status": "prerequisite",
                               "gap_hours": gap_hours(catalog, pre, 1, credit["credit"])}
                stack.append(pre)

    order, seen = [], set()

    def visit(sid: str) -> None:
        if sid in seen:
            return
        seen.add(sid)
        for pre in catalog.skills[sid]["prereqs"]:
            if pre in needed:
                visit(pre)
        order.append(sid)

    for sid in sorted(needed, key=lambda s: (-needed[s]["weight"], needed[s]["gap_hours"])):
        visit(sid)

    hpw = profile.hours_per_week
    steps, cum = [], 0
    for n, sid in enumerate(order, start=1):
        item, skill, s_out = needed[sid], catalog.skills[sid], outlook["skills"][sid]
        hours = max(item["gap_hours"], MIN_STEP_HOURS)
        res = pick_resources(catalog, sid, item["have_level"], hours)
        start = cum
        cum += hours
        steps.append({
            "n": n, "skill": sid, "status": item["status"], "weight": item["weight"],
            "phase": "foundation" if item["status"] == "prerequisite" or item["required_level"] == 1 else (
                "core" if item["weight"] >= 1 else "supporting"),
            "from_level": item["have_level"], "to_level": item["required_level"], "via": item.get("via"),
            "hours": hours, "week_start": math.floor(start / hpw) + 1, "week_end": max(1, math.ceil(cum / hpw)),
            "resource": res["primary"], "alternatives": res["alternatives"], "credential": res["credential"],
            "practice": skill.get("practice"),
            "sdgs": [{"goal": catalog.goal_of(s["target"]), **s} for s in skill.get("sdgs", [])],
            "outlook_pct": pct(s_out["growth"][scenario]), "ring": s_out["ring"][scenario],
        })

    contribution = defaultdict(lambda: {"score": 0.0, "targets": {}})
    for link in role["sdgs"]:
        goal = catalog.goal_of(link["target"])
        contribution[goal]["score"] += 1.0 if link.get("strength") == "direct" else 0.5
        contribution[goal]["targets"][link["target"]] = {"why": link["why"], "via": "role", "strength": link.get("strength")}
    for step in steps:
        for link in step["sdgs"]:
            contribution[link["goal"]]["score"] += 0.25
            contribution[link["goal"]]["targets"].setdefault(link["target"], {"why": link["why"], "via": step["skill"], "strength": "enabling"})
    top = max((c["score"] for c in contribution.values()), default=1.0)
    sdg = sorted(({"goal": g, "score": round(100 * c["score"] / top),
                   "priority": g in profile.sdg_priorities,
                   "targets": [{"target": t, "text": catalog.sdg_targets[t], **v} for t, v in c["targets"].items()]}
                  for g, c in contribution.items()), key=lambda x: -x["score"])

    core = next((i["id"] for i in role["skills"] if i["w"] >= 1), None)
    return {
        "role": rid, "fit_now": round(match["fit"] * 100), "hours_per_week": hpw,
        "total_hours": cum, "weeks": max(1, math.ceil(cum / hpw)) if cum else 0,
        "steps": steps,
        "capstone": {"practice": catalog.skills[core].get("practice") if core else None,
                     "support": catalog.support},
        "sdg_contribution": sdg,
    }
