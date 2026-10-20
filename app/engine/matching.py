"""Explainable role matching.

fit      = importance-weighted share of a role's skill profile the person already covers
           (direct proficiency, or partial credit from related, transferable skills)
outlook  = role demand outlook in the selected scenario, mapped to 0-100
preference = overlap with stated interests and SDG priorities
overall  = weighted mix the user controls (default 50 / 30 / 20)
"""
from pydantic import BaseModel, Field, field_validator

from ..catalog import Catalog, get_catalog
from .forecast import clamp, pct

LEVEL_CREDIT = {0: 0.0, 1: 0.4, 2: 0.75, 3: 1.0}
TRANSFER_CAP = 0.5
TOP_N_ROBUST = 5


class Profile(BaseModel):
    """Only skills, interests and stated preferences. No age, gender, ethnicity or location by design."""
    skills: dict[str, int] = Field(default_factory=dict)
    interests: list[str] = Field(default_factory=list)
    sdg_priorities: list[int] = Field(default_factory=list)
    current_role: str | None = None
    hours_per_week: float = 6.0

    @field_validator("skills")
    @classmethod
    def known_skills(cls, value: dict[str, int]) -> dict[str, int]:
        catalog = get_catalog()
        return {k: int(clamp(v, 0, 3)) for k, v in value.items() if k in catalog.skills and v}

    @field_validator("sdg_priorities")
    @classmethod
    def known_goals(cls, value: list[int]) -> list[int]:
        return sorted({g for g in value if 1 <= g <= 17})

    @field_validator("hours_per_week")
    @classmethod
    def sane_hours(cls, value: float) -> float:
        return clamp(value, 1, 40)


class Weights(BaseModel):
    fit: float = 0.5
    outlook: float = 0.3
    preference: float = 0.2


def required_level(weight: float) -> int:
    return 1 if weight <= 0.25 else 2


def skill_credit(catalog: Catalog, skills: dict[str, int], sid: str, req_level: int) -> dict:
    req = LEVEL_CREDIT[req_level]
    have = skills.get(sid, 0)
    direct = min(1.0, LEVEL_CREDIT[have] / req)
    transfer, via = 0.0, None
    for other, w in catalog.related[sid].items():
        level = skills.get(other, 0)
        if level:
            value = min(TRANSFER_CAP, w * LEVEL_CREDIT[level] / req)
            if value > transfer:
                transfer, via = value, other
    credit = max(direct, transfer)
    return {"have_level": have, "direct": round(direct, 3), "transfer": round(transfer, 3),
            "via": via if transfer > direct else None, "credit": round(credit, 3)}


def gap_hours(catalog: Catalog, sid: str, req_level: int, credit: float) -> int:
    hours_to_working = catalog.skills[sid]["hours"]
    return round(hours_to_working * (LEVEL_CREDIT[req_level] / LEVEL_CREDIT[2]) * (1 - credit))


def match_role(catalog: Catalog, profile: Profile, rid: str) -> dict:
    role = catalog.roles[rid]
    items = []
    for item in role["skills"]:
        req = required_level(item["w"])
        credit = skill_credit(catalog, profile.skills, item["id"], req)
        status = "have" if credit["direct"] >= 1 else ("partial" if credit["credit"] > 0 else "missing")
        items.append({"id": item["id"], "weight": item["w"], "required_level": req, **credit, "status": status,
                      "gap_hours": 0 if status == "have" else gap_hours(catalog, item["id"], req, credit["credit"])})
    total_w = sum(i["weight"] for i in items)
    fit = sum(i["weight"] * i["credit"] for i in items) / total_w
    return {"fit": fit, "items": items, "gap_hours": sum(i["gap_hours"] for i in items)}


def preference_score(catalog: Catalog, profile: Profile, rid: str) -> tuple[float, dict]:
    role = catalog.roles[rid]
    parts = {}
    if profile.interests:
        overlap = set(role["tags"]) & set(profile.interests)
        parts["interests"] = min(1.0, len(overlap) / min(2, len(profile.interests)))
        parts["interest_overlap"] = sorted(overlap)
    goals = {catalog.goal_of(s["target"]) for s in role["sdgs"]}
    if profile.sdg_priorities:
        overlap = goals & set(profile.sdg_priorities)
        parts["sdgs"] = len(overlap) / len(profile.sdg_priorities)
        parts["sdg_overlap"] = sorted(overlap)
    scored = [parts[k] for k in ("interests", "sdgs") if k in parts]
    return (100 * sum(scored) / len(scored) if scored else 50.0), parts


def outlook_score(growth: float) -> float:
    return clamp(50 + 250 * growth, 0, 100)


def score_roles(catalog: Catalog, outlook: dict, profile: Profile, weights: Weights) -> dict[str, dict]:
    wsum = max(1e-9, weights.fit + weights.outlook + weights.preference)
    out = {}
    for rid, role in catalog.roles.items():
        if role["kind"] != "target" or rid == profile.current_role:
            continue
        match = match_role(catalog, profile, rid)
        pref, pref_parts = preference_score(catalog, profile, rid)
        totals = {}
        for scen in catalog.scenarios:
            o = outlook_score(outlook["roles"][rid]["growth"][scen])
            totals[scen] = (weights.fit * match["fit"] * 100 + weights.outlook * o + weights.preference * pref) / wsum
        out[rid] = {"match": match, "preference": pref, "preference_parts": pref_parts, "totals": totals}
    return out


def rank_roles(catalog: Catalog, outlook: dict, profile: Profile, weights: Weights, scenario: str) -> list[dict]:
    scored = score_roles(catalog, outlook, profile, weights)
    ranks = {}
    for scen in catalog.scenarios:
        order = sorted(scored, key=lambda r: -scored[r]["totals"][scen])
        ranks[scen] = {rid: i + 1 for i, rid in enumerate(order)}
    results = []
    for rid, s in scored.items():
        role_out = outlook["roles"][rid]
        by_scen = {scen: ranks[scen][rid] for scen in catalog.scenarios}
        spread = max(by_scen.values()) - min(by_scen.values())
        results.append({
            "id": rid,
            "fit": round(s["match"]["fit"] * 100),
            "preference": round(s["preference"]),
            "preference_parts": s["preference_parts"],
            "outlook_score": round(outlook_score(role_out["growth"][scenario])),
            "total": round(s["totals"][scenario], 1),
            "totals": {k: round(v, 1) for k, v in s["totals"].items()},
            "rank": ranks[scenario][rid],
            "rank_by_scenario": by_scen,
            "robust": all(r <= TOP_N_ROBUST for r in by_scen.values()),
            "scenario_sensitive": spread >= 4,
            "outlook": {scen: {"pct": pct(role_out["growth"][scen]),
                               "low": pct(role_out["growth"][scen] - role_out["band"][scen]),
                               "high": pct(role_out["growth"][scen] + role_out["band"][scen])}
                        for scen in catalog.scenarios},
            "items": s["match"]["items"],
            "gap_hours": s["match"]["gap_hours"],
        })
    results.sort(key=lambda r: r["rank"])
    return results


def current_role_outlook(catalog: Catalog, outlook: dict, profile: Profile) -> dict | None:
    rid = profile.current_role
    if not rid or rid not in catalog.roles:
        return None
    role_out = outlook["roles"][rid]
    return {"id": rid, "wef": role_out["wef"], "wef_dir": role_out["wef_dir"],
            "outlook": {scen: {"pct": pct(role_out["growth"][scen]),
                               "low": pct(role_out["growth"][scen] - role_out["band"][scen]),
                               "high": pct(role_out["growth"][scen] + role_out["band"][scen])}
                        for scen in catalog.scenarios}}
