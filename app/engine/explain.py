"""Grounded explanations. Builds the fact sheet + numbered sources for one recommendation and renders
a deterministic explanation from it. The same fact sheet is the ONLY input the language model gets."""
from ..catalog import Catalog
from .forecast import Signals, pct

SCENARIO_WORDS = {
    "en": {"slow": "slow-disruption", "moderate": "moderate (current-trend)", "fast": "fast-disruption"},
    "ms": {"slow": "gangguan perlahan", "moderate": "sederhana (trend semasa)", "fast": "gangguan pantas"},
    "zh": {"slow": "缓慢颠覆", "moderate": "温和（当前趋势）", "fast": "快速颠覆"},
}


def _name(obj: dict, lang: str) -> str:
    if lang == "en" and obj.get("short"):
        return obj["short"]  # short, plain labels read better in a sentence
    return obj["name"].get(lang) or obj["name"]["en"]


def _title(role: dict, lang: str) -> str:
    return role["title"].get(lang) or role["title"]["en"]


def hn_source_label(signals: Signals, window: list[str]) -> tuple[str, str | None]:
    months = signals.hn["months"]
    picked = [m for m in months if window[0] <= m <= window[1]]
    posts = sum(months[m]["posts"] for m in picked)
    latest = months[picked[-1]] if picked else None
    fetched = (latest or {}).get("fetched_at", "")[:10]
    label = f"Hacker News 'Who is hiring?' job posts {window[0]} to {window[1]} ({posts} posts), fetched {fetched}"
    return label, latest["url"] if latest else None


def build_facts(catalog: Catalog, signals: Signals, outlook: dict, ranked: dict, scenario: str, lang: str) -> dict:
    rid = ranked["id"]
    role = catalog.roles[rid]
    role_out = outlook["roles"][rid]
    sources = [{"id": "S1", "label": "Your profile (self-reported skills or CV)", "url": None}]

    def add(label: str, url: str | None) -> str:
        sid = f"S{len(sources) + 1}"
        sources.append({"id": sid, "label": label, "url": url})
        return sid

    market_skills = [i for i in ranked["items"] if (outlook["skills"][i["id"]]["market"] or {}).get("available")]
    s_hn = None
    if market_skills or (role_out["market"] or {}).get("available"):
        window = (outlook["skills"][market_skills[0]["id"]]["market"] if market_skills else role_out["market"])["window_recent"]
        s_hn = add(*hn_source_label(signals, window))
    caps = outlook["capabilities"]
    s_oa = None
    if any(outlook["skills"][i["id"]]["drivers"] for i in ranked["items"]):
        s_oa = add(f"OpenAlex research index, AI-capability topics {caps['bucket_base']} vs {caps['bucket_recent']}, "
                   f"fetched {(caps.get('fetched_at') or '')[:10]}", "https://openalex.org/")
    s_wef = None
    if role.get("wef"):
        claim = catalog.claims[role["wef"]]
        src = catalog.sources[claim["source"]]
        s_wef = add(f"{src['title']} ({src['date']}): {claim['text']}", src["url"])
    if role["taxonomy"].get("onet"):
        add(f"O*NET {role['taxonomy']['onet']} {role['taxonomy']['onet_title']}",
            f"https://www.onetonline.org/link/summary/{role['taxonomy']['onet']}")
    s_sdg = add("UN Sustainable Development Goals: official targets", "https://sdgs.un.org/goals")
    s_model = add("Path.AI scenario model: assumptions published in data/catalog/capabilities.json", None)

    have = [i for i in ranked["items"] if i["status"] == "have"]
    transfer = [i for i in ranked["items"] if i["status"] == "partial" and i["via"]]
    gaps = sorted((i for i in ranked["items"] if i["status"] != "have"), key=lambda i: (-i["weight"], i["gap_hours"]))
    drivers = []
    for contrib in role_out["contributions"][:2]:
        sk = outlook["skills"][contrib["skill"]]
        market = sk["market"] or {}
        entry = {"skill": _name(catalog.skills[contrib["skill"]], lang),
                 "skill_outlook_pct": pct(sk["growth"][scenario])}
        if market.get("available"):
            entry["job_post_share_change_pct"] = pct(market["raw_momentum"])
            entry["job_post_source"] = s_hn
        if sk["drivers"]:
            d = sk["drivers"][0]
            entry["ai_capability"] = d["label"]
            entry["ai_capability_research_share_change_pct"] = pct(d["momentum"])
            entry["ai_relation"] = "complements" if d["sensitivity"] > 0 else "substitutes"
            entry["ai_source"] = s_oa
        drivers.append(entry)
    o = ranked["outlook"][scenario]
    return {
        "role": _title(role, lang),
        "role_summary": role["summary"],
        "fit_pct": ranked["fit"],
        "skills_you_have": [_name(catalog.skills[i["id"]], lang) for i in have],
        "transferable": [{"skill": _name(catalog.skills[i["id"]], lang), "from": _name(catalog.skills[i["via"]], lang)}
                         for i in transfer],
        "main_gaps": [_name(catalog.skills[i["id"]], lang) for i in gaps[:3]],
        "gap_hours_total": ranked["gap_hours"],
        "scenario": SCENARIO_WORDS.get(lang, SCENARIO_WORDS["en"])[scenario],
        "outlook_pct_per_year": o["pct"], "outlook_low_pct": o["low"], "outlook_high_pct": o["high"],
        "robust_across_scenarios": ranked["robust"],
        "wef_claim": catalog.claims[role["wef"]]["text"] if role.get("wef") else None,
        "drivers": drivers,
        "sdg_targets": [{"target": s["target"], "why": s["why"]} for s in role["sdgs"]],
        "citations": {"profile": "S1", "job_posts": s_hn, "research": s_oa, "wef": s_wef, "sdg": s_sdg, "model": s_model},
        "sources": sources,
    }


def _signed(x: float) -> str:
    return f"{x:+.0f}%"


def template_explanation(facts: dict, lang: str = "en") -> str:
    c = facts["citations"]
    gaps = ", ".join(facts["main_gaps"]) or "-"
    sdgs = ", ".join(s["target"] for s in facts["sdg_targets"])
    rng = f"{_signed(facts['outlook_low_pct'])} … {_signed(facts['outlook_high_pct'])}"
    trend_cites = "".join(f"[{x}]" for x in (c["job_posts"], c["research"], c["model"]) if x)
    driver = facts["drivers"][0] if facts["drivers"] else None
    if lang == "ms":
        parts = [f"Anda sudah memenuhi {facts['fit_pct']}% profil kemahiran {facts['role']} [{c['profile']}].",
                 f"Jurang utama: {gaps} (kira-kira {facts['gap_hours_total']} jam pembelajaran).",
                 f"Dalam senario {facts['scenario']}, permintaan dianggarkan {_signed(facts['outlook_pct_per_year'])} setahun (julat {rng}) {trend_cites}."]
        if facts["wef_claim"]:
            parts.append(f"WEF 2025 menyenaraikan peranan ini antara yang paling pesat berkembang [{c['wef']}].")
        parts.append(f"Peranan ini menyumbang kepada sasaran SDG {sdgs} [{c['sdg']}]. Ini anggaran, bukan ramalan — keputusan di tangan anda.")
        return " ".join(parts)
    if lang == "zh":
        parts = [f"你已具备{facts['role']}所需技能的 {facts['fit_pct']}% [{c['profile']}]。",
                 f"主要差距：{gaps}（约 {facts['gap_hours_total']} 学习小时）。",
                 f"在{facts['scenario']}情景下，需求预计每年 {_signed(facts['outlook_pct_per_year'])}（区间 {rng}）{trend_cites}。"]
        if facts["wef_claim"]:
            parts.append(f"世界经济论坛 2025 报告将该职位列为增长最快的职位之一 [{c['wef']}]。")
        parts.append(f"该职位有助于实现可持续发展目标 {sdgs} [{c['sdg']}]。这只是估计，不是预言——由你做决定。")
        return " ".join(parts)
    parts = [f"You already cover {facts['fit_pct']}% of the {facts['role']} skill profile [{c['profile']}]"]
    if facts["transferable"]:
        t = facts["transferable"][0]
        parts[0] += f", with partial credit for {t['skill']} thanks to your {t['from']} skills"
    parts[0] += "."
    parts.append(f"Main gaps: {gaps} (about {facts['gap_hours_total']} learning hours).")
    parts.append(f"In the {facts['scenario']} scenario, demand is estimated at {_signed(facts['outlook_pct_per_year'])} per year "
                 f"(range {rng}) {trend_cites}.")
    if driver and "job_post_share_change_pct" in driver:
        parts.append(f"Biggest driver: {driver['skill']}, whose share of job posts changed "
                     f"{_signed(driver['job_post_share_change_pct'])} year-on-year [{driver['job_post_source']}].")
    elif driver and "ai_capability" in driver:
        parts.append(f"Biggest AI driver: {driver['ai_capability']} (research share "
                     f"{_signed(driver['ai_capability_research_share_change_pct'])} year-on-year), which "
                     f"{driver['ai_relation']} {driver['skill']} [{driver['ai_source']}].")
    if facts["wef_claim"]:
        parts.append(f"{facts['wef_claim'].rstrip('.')} [{c['wef']}].")
    parts.append(f"This role contributes to SDG targets {sdgs} [{c['sdg']}]. "
                 "This is an estimate, not a prediction — the decision is yours.")
    return " ".join(parts)
