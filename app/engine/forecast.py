"""Turns live trend signals into skill and role outlooks under three AI-disruption scenarios.

For every skill s and scenario k (annual log-growth of demand):

    growth[s,k] = market_weight * momentum_s                    # live job-post signal (HN), shrunk
                + prior_step * [s has a cited WEF 'rising' claim] # baseline
                + pace_k * sum_c sensitivity[s,c] * (1 + clip(capability_momentum_c))   # AI pressure

Role outlook = importance-weighted mean of its skills' growth + WEF role prior + a small role-title
job-post term. Every number carries the source it came from, so the UI can show it.
"""
import math

from ..catalog import Catalog
from ..signals.store import HN_FILE, META_FILE, OPENALEX_FILE, read_json


def month_add(month: str, k: int) -> str:
    year, mon = map(int, month.split("-"))
    idx = year * 12 + (mon - 1) + k
    return f"{idx // 12:04d}-{idx % 12 + 1:02d}"


def month_window(end: str, n: int) -> list[str]:
    return [month_add(end, -i) for i in reversed(range(n))]


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def pct(g: float) -> float:
    """Annual log-growth -> percent change per year."""
    return round((math.exp(g) - 1) * 100, 1)


class Signals:
    """In-memory view of the cached trend data (reloaded after every refresh)."""

    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        self.hn = read_json(HN_FILE, {"months": {}})
        self.openalex = read_json(OPENALEX_FILE, {"buckets": {}})
        self.meta = read_json(META_FILE, {})

    @property
    def months(self) -> list[str]:
        return sorted(self.hn["months"])

    def as_of_options(self) -> list[str]:
        """Months with the 18 months of history needed for a year-over-year comparison."""
        have = set(self.months)
        return [m for m in self.months if all(x in have for x in month_window(m, 18))]

    def latest(self) -> str | None:
        options = self.as_of_options()
        return options[-1] if options else None


def hn_stats(signals: Signals, kind: str, key: str, as_of: str, model: dict) -> dict:
    """Year-over-year change in the share of job posts mentioning `key` (last 6 months vs a year earlier)."""
    recent, base = month_window(as_of, 6), month_window(month_add(as_of, -12), 6)
    months = signals.hn["months"]

    def agg(window):
        posts = sum(months[m]["posts"] for m in window if m in months)
        hits = sum(months[m][kind].get(key, 0) for m in window if m in months)
        return posts, hits

    n_r, c_r = agg(recent)
    n_b, c_b = agg(base)
    out = {"available": False, "mentions_recent": c_r, "mentions_base": c_b, "posts_recent": n_r, "posts_base": n_b,
           "share_recent": c_r / n_r if n_r else 0.0, "share_base": c_b / n_b if n_b else 0.0,
           "window_recent": [recent[0], recent[-1]], "window_base": [base[0], base[-1]]}
    if not n_r or not n_b or c_r + c_b < model["min_mentions_for_market_signal"]:
        return out
    raw = math.log((c_r + 0.5) / n_r) - math.log((c_b + 0.5) / n_b)
    se = math.sqrt(1 / (c_r + 0.5) + 1 / (c_b + 0.5))
    tau2 = model["momentum_prior_sd"] ** 2
    shrink = tau2 / (tau2 + se * se)  # empirical-Bayes: noisy (small-count) signals move less
    clip = model["market_momentum_clip"]  # one hot year should not dominate a multi-year outlook
    out.update(available=True, raw_momentum=raw, momentum=clamp(raw, -clip, clip) * shrink, se=se * shrink, shrink=shrink)
    return out


def hn_sparkline(signals: Signals, kind: str, key: str, as_of: str, n: int = 24) -> list[dict]:
    months = signals.hn["months"]
    points = []
    for m in month_window(as_of, n):
        window = [x for x in month_window(m, 3) if x in months]
        posts = sum(months[x]["posts"] for x in window)
        hits = sum(months[x][kind].get(key, 0) for x in window)
        if posts:
            points.append({"month": m, "share": round(hits / posts, 4)})
    return points


def last_complete_half(as_of: str) -> str:
    year, mon = map(int, as_of.split("-"))
    if mon == 12:
        return f"{year}H2"
    return f"{year}H1" if mon >= 6 else f"{year - 1}H2"


def year_before(half: str) -> str:
    return f"{int(half[:4]) - 1}{half[4:]}"


def capability_stats(signals: Signals, catalog: Catalog, as_of: str) -> dict:
    buckets = signals.openalex.get("buckets", {})
    recent = last_complete_half(as_of)
    base = year_before(recent)
    out = {}
    br, bb = buckets.get(recent, {}).get("counts", {}), buckets.get(base, {}).get("counts", {})
    field = None
    if br.get("baseline") and bb.get("baseline"):
        field = {"growth": math.log(br["baseline"] / bb["baseline"]), "recent": br["baseline"], "base": bb["baseline"]}
    for cap in catalog.capabilities:
        cid = cap["id"]
        entry = {"id": cid, "label": cap["label"], "query": cap["query"], "available": False,
                 "bucket_recent": recent, "bucket_base": base}
        if field and br.get(cid) and bb.get(cid):
            share_r, share_b = br[cid] / br["baseline"], bb[cid] / bb["baseline"]
            entry.update(available=True, count_recent=br[cid], count_base=bb[cid], share_recent=share_r,
                         share_base=share_b, momentum=math.log(share_r / share_b),
                         series=[{"bucket": b, "count": buckets[b]["counts"].get(cid),
                                  "share": round(buckets[b]["counts"].get(cid, 0) / buckets[b]["counts"]["baseline"], 4)}
                                 for b in sorted(buckets) if buckets[b]["counts"].get("baseline")])
        out[cid] = entry
    return {"topics": out, "field": field, "bucket_recent": recent, "bucket_base": base,
            "fetched_at": buckets.get(recent, {}).get("fetched_at")}


def ring_of(g: float, rings: dict) -> str:
    if g >= rings["surging"]:
        return "surging"
    if g >= rings["rising"]:
        return "rising"
    if g < rings["declining"]:
        return "declining"
    return "stable"


def compute_outlook(catalog: Catalog, signals: Signals, as_of: str) -> dict:
    model = catalog.model
    lo, hi = model["capability_momentum_clip"]
    caps = capability_stats(signals, catalog, as_of)
    skills = {}
    for sid, skill in catalog.skills.items():
        market = hn_stats(signals, "skills", sid, as_of, model) if skill.get("hn") else None
        has_market = bool(market and market["available"])
        market_term = model["market_weight"] * market["momentum"] if has_market else 0.0
        prior_term = model["prior_step"] if skill.get("wef") else 0.0
        drivers, ai_base = [], 0.0
        for cap_id, sensitivity in skill.get("ai", {}).items():
            cap = caps["topics"][cap_id]
            momentum = clamp(cap["momentum"], lo, hi) if cap["available"] else 0.0
            effect = sensitivity * (1 + momentum)
            ai_base += effect
            drivers.append({"capability": cap_id, "label": cap["label"], "sensitivity": sensitivity,
                            "momentum": round(momentum, 3), "effect": round(effect, 4)})
        growth, band, ring = {}, {}, {}
        for scen_id, scen in catalog.scenarios.items():
            ai_term = scen["pace"] * ai_base
            g = market_term + prior_term + ai_term
            se_market = model["market_weight"] * market["se"] if has_market else 0.0
            floor = 0.01 if has_market else 0.03  # baseline-only skills are less certain
            growth[scen_id] = g
            band[scen_id] = math.sqrt(se_market ** 2 + (0.25 * ai_term) ** 2 + floor ** 2)
            ring[scen_id] = ring_of(g, model["rings"])
        confidence = "high" if has_market and market["mentions_recent"] + market["mentions_base"] >= 150 else (
            "medium" if has_market else "low")
        skills[sid] = {"growth": growth, "band": band, "ring": ring, "confidence": confidence,
                       "components": {"market": market_term, "prior": prior_term, "ai_base": ai_base},
                       "market": market, "drivers": sorted(drivers, key=lambda d: -abs(d["effect"])),
                       "wef": skill.get("wef")}

    roles = {}
    for rid, role in catalog.roles.items():
        total_w = sum(i["w"] for i in role["skills"])
        prior = {"growing": model["role_prior_growing"], "declining": model["role_prior_declining"]}.get(role.get("wef_dir"), 0.0)
        market = hn_stats(signals, "roles", rid, as_of, model) if role.get("hn") else None
        has_market = bool(market and market["available"])
        role_market_term = 0.5 * model["market_weight"] * market["momentum"] if has_market else 0.0
        growth, band = {}, {}
        for scen_id in catalog.scenarios:
            skill_part = sum(i["w"] * skills[i["id"]]["growth"][scen_id] for i in role["skills"]) / total_w
            growth[scen_id] = skill_part + prior + role_market_term
            band[scen_id] = sum(i["w"] * skills[i["id"]]["band"][scen_id] for i in role["skills"]) / total_w
        contributions = sorted(
            ({"skill": i["id"], "weight": i["w"], "value": i["w"] * skills[i["id"]]["growth"]["moderate"] / total_w}
             for i in role["skills"]), key=lambda c: -abs(c["value"]))
        roles[rid] = {"growth": growth, "band": band, "prior": prior, "wef": role.get("wef"),
                      "wef_dir": role.get("wef_dir"), "market": market, "market_term": role_market_term,
                      "contributions": contributions}
    return {"as_of": as_of, "skills": skills, "roles": roles, "capabilities": caps}
