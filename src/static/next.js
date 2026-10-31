// Opportunities: the last step of the journey. Two questions (study or work? where?), then open jobs matched to the
// person's skills — with the Path.AI courses that close the gap — or the universities of that country, how to apply
// and how to fund it. The answers stay in this browser; the profile is sent with each request, as on the matches page.
import { h } from "./charts.js";
import { state, saveProfile, DEFAULT_LANGUAGES, toast, store, t, api, loc, skillShort, roleTitle, roleById, hasProfile, icon, rerender, dateLabel,
  ensureMatches, ensureCourses, aiSource} from "./core.js";
import { hoursLabel } from "./learn.js";

const POPULAR = {
  study: ["MY", "SG", "GB", "AU", "US", "CA", "DE", "NL", "IE", "NZ", "JP", "KR", "CN", "FR", "TR"],
  work: ["MY", "SG", "REMOTE", "GB", "US", "DE", "AU", "CA", "NL", "IE", "JP", "AE", "IN"],
};
const ALIASES = { uk: "GB", britain: "GB", "great britain": "GB", england: "GB", scotland: "GB", usa: "US", america: "US", uae: "AE",
  emirates: "AE", dubai: "AE", korea: "KR", holland: "NL", turkey: "TR", turkiye: "TR", russia: "RU", vietnam: "VN", czechia: "CZ" };
const LOCALES = { en: "en", ms: "ms", zh: "zh-CN" };
const FEEDS = { hn: ["Hacker News", "https://news.ycombinator.com/"], himalayas: ["Himalayas", "https://himalayas.app/"],
  jobicy: ["Jobicy", "https://jobicy.com/"], remotive: ["Remotive", "https://remotive.com/"], arbeitnow: ["Arbeitnow", "https://www.arbeitnow.com/"],
  remoteok: ["Remote OK", "https://remoteok.com/"] };
const LEVELS = ["any", "early", "mid", "senior"];

// ---------------------------------------------------------------- helpers
const namers = {};
export function countryName(code, lang = state.lang) {
  if (code === "REMOTE") return t("nx_remote_any");
  try {
    namers[lang] ||= new Intl.DisplayNames([LOCALES[lang] || "en"], { type: "region" });
    return namers[lang].of(code) || code;
  } catch { return code; }
}
// English puts "the" before some country names inside a sentence ("Jobs for you in the United Kingdom").
const THE = new Set(["GB", "US", "NL", "PH", "AE", "CZ", "BS", "GM", "MV", "MH", "SB", "KY", "FO", "FK", "CF", "KM", "DO", "VA", "CD", "CG", "TC", "VG", "VI", "MP", "SC"]);
const inCountry = (code) => (state.lang === "en" && THE.has(code) ? `the ${countryName(code)}` : countryName(code));
// Flags are small SVG images (flag-icons, MIT; static/flags): Windows has no colour flag emoji and would show "MY", "SG".
const flag = (code) => (/^[A-Z]{2}$/.test(code)
  ? h("img", { class: "flag", src: `/static/flags/${code.toLowerCase()}.svg`, alt: "", width: 20, height: 15, loading: "lazy", decoding: "async",
    onerror: (e) => e.currentTarget.remove() })
  : null);
const fold = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const hostOf = (url) => { try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return ""; } };
const isStudent = () => state.origin?.type === "field" || state.wizard.student;
const ext = (href, ...children) => h("a", { href, target: "_blank", rel: "noopener" }, ...children);

// What the model read in the posting (scripts/opportunities/enrich.py): one short line, every fact checked against the text.
const langNamers = {};
function languageName(code) {
  try {
    langNamers[state.lang] ||= new Intl.DisplayNames([LOCALES[state.lang] || "en"], { type: "language" });
    return langNamers[state.lang].of(code) || code;
  } catch { return code; }
}
const MONEY_LOCALES = { en: "en-MY", ms: "ms-MY", zh: "en-MY" };   // "RM 3,500–4,500", "US$120,000–150,000"
function payText([min, max, currency, per]) {
  let text;
  try {
    const fmt = new Intl.NumberFormat(MONEY_LOCALES[state.lang] || "en-MY", { style: "currency", currency, maximumFractionDigits: 0 });
    text = max && max !== min ? (fmt.formatRange ? fmt.formatRange(min, max) : `${fmt.format(min)}–${fmt.format(max)}`) : fmt.format(min);
  } catch {
    text = `${currency} ${Math.round(min).toLocaleString()}${max && max !== min ? `–${Math.round(max).toLocaleString()}` : ""}`;
  }
  return `${text} ${t(`nx_per_${per}`)}`;
}
function requirements(j) {
  const check = Object.fromEntries((j.checks || []).map((c) => [c.kind, c]));
  if (!j.ai && !check.languages) return null;
  const ai = j.ai || {};
  // ok: the person meets it · false: they do not (named, and it lowers the fit) · null: they have not said
  const mark = (text, ok) => h("span", { class: ok === false ? "warn" : ok ? "ok" : null }, ok === false ? "⚠ " : ok ? "✓ " : "", text);
  const bits = [];
  const sk = check.skills;
  if (sk && ai.req?.length && sk.of && sk.have === sk.of) bits.push(mark(t("nx_chk_all", { n: sk.of }), true));   // gaps show below
  if (ai.years != null) {
    const c = check.years;
    bits.push(mark(c?.ok === false ? t("nx_chk_years_short", { n: ai.years, m: c.have }) : ai.years === 0 ? t("nx_req_no_exp") : t("nx_req_years", { n: ai.years }), c?.ok ?? null));
  }
  if (ai.degree) bits.push(mark(ai.degree_required === false ? `${t(`nx_deg_${ai.degree}`)} (${t("nx_req_preferred")})` : t(`nx_deg_${ai.degree}`), null));
  const langs = check.languages?.need || ai.languages || [];      // incl. a language the job title names
  if (langs.length) {
    const c = check.languages;
    bits.push(mark(c?.missing?.length ? t("nx_chk_needs", { langs: c.missing.map(languageName).join(", ") }) : langs.map(languageName).join(", "), c?.ok ?? null));
  }
  if (ai.pay) bits.push(mark(payText(ai.pay), null));
  if (ai.mode && ai.mode !== "remote") bits.push(mark(t(`nx_mode_${ai.mode}`), null));
  if (ai.visa != null) bits.push(mark(t(ai.visa ? "nx_visa_yes" : "nx_visa_no"), null));
  return bits.length ? h("p", { class: "job-req", title: t("nx_ai_read") }, icon("sparkles"), h("span", {}, bits.flatMap((b, i) => (i ? [" · ", b] : [b])))) : null;
}

// The person's experience and languages, compared only with what postings explicitly ask for. Prefilled; one tap changes.
const EXPERIENCE = [[0, 0, 0, "nx_exp_0"], [2, 1, 2, "nx_exp_2"], [4, 3, 5, "nx_exp_4"], [7, 6, 9, "nx_exp_7"], [10, 10, 99, "nx_exp_10"]];
const MAIN_LANGS = ["en", "ms", "zh", "ta"];
const MORE_LANGS = ["de", "fr", "es", "ja", "ko", "ar", "hi", "id", "th", "vi", "nl", "pt"];
const myLanguages = () => state.profile.languages || DEFAULT_LANGUAGES;
export function aboutYou() {        // also on My profile
  const p = state.profile;
  const years = p.years_experience ?? null;
  const langs = myLanguages();
  const setYears = (value, on) => { p.years_experience = on ? null : value; saveProfile(); rerender(); };
  const toggle = (code) => { p.languages = langs.includes(code) ? langs.filter((x) => x !== code) : [...langs, code]; saveProfile(); rerender(); };
  const shown = state.nextUi.moreLangs ? [...MAIN_LANGS, ...MORE_LANGS] : [...new Set([...MAIN_LANGS, ...langs])];
  return h("div", { class: "about-you" },
    h("div", { class: "row" }, h("span", { class: "k" }, t("nx_exp_label")),
      EXPERIENCE.map(([value, lo, hi, key]) => {
        const on = years != null && years >= lo && years <= hi;
        return h("button", { type: "button", class: `chip-sm${on ? " on" : ""}`, "aria-pressed": String(on), onclick: () => setYears(value, on) }, t(key));
      })),
    h("div", { class: "row" }, h("span", { class: "k" }, t("nx_lang_label")),
      shown.map((code) => h("button", { type: "button", class: `chip-sm${langs.includes(code) ? " on" : ""}`, "aria-pressed": String(langs.includes(code)),
        onclick: () => toggle(code) }, languageName(code))),
      state.nextUi.moreLangs ? null : h("button", { type: "button", class: "chip-sm more", onclick: () => { state.nextUi.moreLangs = true; rerender(); } }, `${t("nx_more")} +`)));
}

// The market for the chosen direction: what its postings ask for, read by the model, and how much of it the person covers.
const roundPay = (x) => (x >= 10000 ? Math.round(x / 1000) * 1000 : x);
function marketPanel() {
  const m = state.nextMarket;
  if (!m || !hasProfile()) return null;
  const pc = (x) => Math.round(100 * x);
  const ours = new Set((state.courses || []).map((c) => c.skill));
  const counts = [m.country === "REMOTE" ? t("mk_here_remote", { n: m.here.n }) : t("mk_here", { n: m.here.n, where: inCountry(m.country) }),
    t("mk_world", { n: m.world.n.toLocaleString() })];
  if (m.outlook_pct != null) counts.push(t("mk_trend", { pct: `${m.outlook_pct > 0 ? "+" : ""}${Math.round(m.outlook_pct)}%` }));
  if (m.basis === "none") {
    return h("section", { class: "market" }, h("p", { class: "k" }, t("mk_title", { role: roleTitle(m.role) })),
      h("p", { class: "market-counts" }, counts.join(" · ")), h("p", { class: "small muted" }, t("mk_too_few")));
  }
  const b = m[m.basis];
  const asks = [];
  if (b.years) asks.push(t("mk_years", { n: b.years.median }));
  if (b.read) asks.push(t("mk_degree", { n: pc(b.degree_share) }));
  for (const l of b.languages.slice(0, 2)) asks.push(`${languageName(l.code)} ${pc(l.share)}%`);
  const ai = state.marketAdvice?.[state.nextMarketKey];
  return h("section", { class: "market" },
    h("p", { class: "k" }, t("mk_title", { role: roleTitle(m.role) })),
    h("p", { class: "market-counts" }, counts.join(" · ")),
    m.basis === "world" ? h("p", { class: "small muted" }, t("mk_world_basis")) : null,
    b.coverage != null ? [h("p", { class: "market-cover" }, t("mk_cover", { n: pc(b.coverage) })),
      h("div", { class: "bar", role: "img", "aria-label": `${pc(b.coverage)}%` }, h("span", { style: { width: `${pc(b.coverage)}%` } }))] : null,
    b.skills.length ? h("div", { class: "row job-skills" }, h("span", { class: "k" }, t("mk_skills")),
      b.skills.slice(0, 6).map((s) => (s.you ? h("span", { class: "pill have" }, "✓ ", skillShort(s.id), ` · ${pc(s.share)}%`)
        : ours.has(s.id) ? h("a", { class: "pill learn", href: `#/learn/${s.id}` }, `${skillShort(s.id)} · ${pc(s.share)}% →`)
          : h("span", { class: "pill" }, `${skillShort(s.id)} · ${pc(s.share)}%`)))) : null,
    asks.length ? h("p", { class: "small" }, h("b", {}, `${t("mk_asks")}: `), asks.join(" · ")) : null,
    h("p", { class: "small" }, b.pay ? t(m.basis === "world" ? "mk_pay_world" : "mk_pay", { range: payText([roundPay(b.pay.low), roundPay(b.pay.high), b.pay.currency, b.pay.per]), n: b.pay.n }) : t("mk_pay_none")),
    ai?.off ? h("div", { class: "job-ai off" }, h("p", {}, t("mk_ai_off")))
      : ai ? h("div", { class: "job-ai" }, h("p", {}, ai.text), h("p", { class: "tiny muted" }, t("nx_ai_note", { model: ai.model }), aiSource(ai.source)))
        : h("div", {}, h("button", { type: "button", class: "btn btn-secondary btn-sm", onclick: (e) => askMarket(e.currentTarget) }, icon("sparkles"), t("mk_ai"))));
}

async function askMarket(btn) {
  btn.disabled = true;
  btn.textContent = t("nx_asking");
  const key = state.nextMarketKey;
  try {
    const res = await api("/api/next/market/ai", JSON.parse(key));
    if (res.engine === "llm") (state.marketAdvice ||= {})[key] = res;
    else if (res.guardrail?.rejected) toast(t("nx_ai_rejected"));
    else (state.marketAdvice ||= {})[key] = { off: true };
  } catch (e) { toast(String(e.message || e)); }
  rerender();
}

async function askAI(j, btn) {
  btn.disabled = true;
  btn.textContent = t("nx_asking");
  try {
    const res = await api("/api/next/why", { profile: { ...state.profile, languages: myLanguages() }, certified: Object.keys(state.certs), job_id: j.id, lang: state.lang });
    if (res.engine === "llm") (state.jobAdvice ||= {})[j.id] = res;
    else if (res.guardrail?.rejected) toast(t("nx_ai_rejected"));
    else (state.jobAdvice ||= {})[j.id] = { off: true };      // GPU off and nothing saved for this job: say so here
  } catch (e) { toast(String(e.message || e)); }
  rerender();
}

function posted(iso) {
  if (!iso) return "";
  const days = Math.max(0, Math.round((Date.now() - Date.parse(`${iso}T00:00:00Z`)) / 864e5));
  const rtf = new Intl.RelativeTimeFormat(LOCALES[state.lang], { numeric: "auto" });
  if (days < 14) return rtf.format(-days, "day");
  if (days < 60) return rtf.format(-Math.round(days / 7), "week");
  return rtf.format(-Math.round(days / 30), "month");
}

// The person's directions: the role they last opened a plan for, their best matches, and the job they do now
// (postings for it are often the ones they can apply for today).
function directions() {
  const out = [];
  const focus = store.get("focusRole", null);
  if (focus && roleById()[focus]) out.push(focus);
  for (const r of (hasProfile() && state.matches?.roles) || []) if (out.length < 4) out.push(r.id);
  if (state.profile.current_role && roleById()[state.profile.current_role]) out.push(state.profile.current_role);
  return [...new Set(out)].slice(0, 5);
}

function countryOk(mode, code) {
  if (!code) return false;
  if (code === "REMOTE") return mode === "work";
  const c = state.nextMeta?.countries.find((x) => x.code === code);
  return !!c && (mode === "work" ? c.jobs + c.remote > 0 : c.universities > 0);
}

function saveNext() { store.set("next", state.next); }

function pickMode(mode) {
  state.next.mode = mode;
  if (!countryOk(mode, state.next.country)) state.next.country = null;
  saveNext();
  rerender();
  requestAnimationFrame(() => document.getElementById("nx-country")?.focus({ preventScroll: true }));
}

function pickCountry(code) {
  state.next.country = code;
  state.nextUi = { ...state.nextUi, editing: false, q: "", tab: "local", uniQ: "", uniShown: 20, allFields: false };
  saveNext();
  if (location.hash !== "#/next") history.replaceState(null, "", "#/next"); // drop ?mode=… so it is not re-applied
  rerender();
}

// Switching study <-> work keeps the country when it makes sense, otherwise asks for it again.
function switchMode(mode) {
  if (mode === state.next.mode) return;
  state.next.mode = mode;
  state.nextUi.editing = !countryOk(mode, state.next.country);
  saveNext();
  rerender();
}

// ---------------------------------------------------------------- data
export async function ensureNext() {
  if (!state.nextMeta) state.nextMeta = await api("/api/next/meta");
  const { mode, country } = state.next;
  if (!mode || !countryOk(mode, country) || state.nextUi.editing) return;
  if (hasProfile()) await ensureMatches();
  await ensureCourses();
  if (mode === "work") {
    const dirs = directions();
    const roles = dirs.includes(state.nextUi.role) ? [state.nextUi.role] : dirs;
    const body = { profile: { ...state.profile, languages: myLanguages() }, certified: Object.keys(state.certs), country, roles, level: state.nextUi.level, lang: state.lang,
      country_name: country === "REMOTE" ? "" : countryName(country, "en") };
    const key = JSON.stringify(body);
    if (state.nextJobsKey !== key) {
      state.nextJobs = await api("/api/next/jobs", body);
      state.nextJobsKey = key;
    }
    const marketRole = dirs.includes(state.nextUi.role) ? state.nextUi.role : dirs[0];
    if (marketRole && hasProfile()) {
      const mbody = { profile: body.profile, certified: body.certified, country, role: marketRole, lang: state.lang, country_name: body.country_name };
      const mkey = JSON.stringify(mbody);
      if (state.nextMarketKey !== mkey) {
        try { state.nextMarket = await api("/api/next/market", mbody); } catch { state.nextMarket = null; }   // optional panel
        state.nextMarketKey = mkey;
      }
    } else state.nextMarket = null;
  } else {
    const body = { country, roles: directions(), study_field: state.origin?.type === "field" ? state.origin.id : null };
    const key = JSON.stringify(body);
    if (state.nextStudyKey !== key) {
      state.nextStudy = await api("/api/next/study", body);
      state.nextStudyKey = key;
      state.nextUi.field = state.nextStudy.recommended[0];
    }
  }
}

export function viewNext() {
  const { mode, country } = state.next;
  if (!mode || !countryOk(mode, country) || state.nextUi.editing) return viewQuestions();
  return mode === "work" ? viewJobs() : viewStudy();
}

// ---------------------------------------------------------------- the two questions
function countryMatches(mode, query) {
  const q = fold(query.trim());
  if (!q) return [];
  const alias = ALIASES[q];
  const size = (c) => (mode === "work" ? c.jobs + c.remote : c.universities);
  return state.nextMeta.countries
    .filter((c) => countryOk(mode, c.code))
    .map((c) => {
      const names = [fold(countryName(c.code)), fold(countryName(c.code, "en"))];
      const rank = c.code === alias || c.code.toLowerCase() === q ? 0 : names.some((n) => n.startsWith(q)) ? 1 : names.some((n) => n.includes(q)) ? 2 : 9;
      return { ...c, rank };
    })
    .filter((c) => c.rank < 9)
    .sort((a, b) => a.rank - b.rank || size(b) - size(a))
    .slice(0, 8);
}

function countryPicker(mode) {
  const hint = (c) => (mode === "work" ? t("nx_n_jobs", { n: (c.jobs + c.remote).toLocaleString() }) : t("nx_n_unis", { n: c.universities.toLocaleString() }));
  const list = h("div", {});
  const fill = (query) => {
    if (!query.trim()) { list.replaceChildren(); return; }
    const found = countryMatches(mode, query);
    list.replaceChildren(found.length
      ? h("div", { class: "suggest", role: "listbox" }, found.map((c) => h("button", { type: "button", role: "option", onclick: () => pickCountry(c.code) },
        h("span", { class: "country-opt" }, flag(c.code), countryName(c.code)), h("span", { class: "hint" }, hint(c)))))
      : h("p", { class: "small muted", style: { marginTop: "10px" } }, t("nx_no_country", { q: query })));
  };
  fill(state.nextUi.q);
  const input = h("input", { id: "nx-country", type: "search", placeholder: t("nx_country_search"), "aria-label": t("nx_country_search"), value: state.nextUi.q,
    autocomplete: "off", oninput: (e) => { state.nextUi.q = e.target.value; fill(e.target.value); },
    onkeydown: (e) => { if (e.key === "Enter") { const first = countryMatches(mode, state.nextUi.q)[0]; if (first) pickCountry(first.code); } } });
  const chip = (code) => h("button", { type: "button", class: `chip ${state.next.country === code ? "on" : ""}`, "aria-pressed": String(state.next.country === code),
    onclick: () => pickCountry(code) }, code === "REMOTE" ? [icon("globe"), t("nx_remote_any")] : [flag(code), countryName(code)]);
  return [
    h("h2", { class: "q2" }, t(mode === "work" ? "nx_q2_work" : "nx_q2_study")),
    h("div", { class: "search" }, icon("search"), input), list,
    h("div", { class: "label" }, t("nx_popular")),
    h("div", { class: "chips" }, POPULAR[mode].filter((code) => countryOk(mode, code)).map(chip)),
  ];
}

function viewQuestions() {
  const mode = state.next.mode;
  const choice = (id, ic) => {
    const on = mode === id;
    return h("button", { type: "button", class: `choice ${on ? "on" : ""}`, "aria-pressed": String(on), onclick: () => pickMode(id) },
      h("span", { class: "icon-circle" }, icon(ic)),
      h("span", { class: "c-text" }, h("b", {}, t(`nx_${id}`)), h("span", {}, t(`nx_${id}_d`))),
      id === "study" && isStudent() ? h("span", { class: "badge best" }, t("nx_for_students")) : null);
  };
  const canGoBack = state.nextUi.editing && countryOk(state.next.mode, state.next.country);
  return h("div", { class: "container" }, h("section", { class: "wizard next-q" },
    h("h1", {}, t("nx_q1")), h("p", { class: "sub" }, t("nx_q1_sub")),
    h("div", { class: "choices" }, choice("study", "grad"), choice("work", "briefcase")),
    mode ? countryPicker(mode) : null,
    canGoBack ? h("div", { class: "wizard-actions" },
      h("button", { type: "button", class: "btn btn-link", onclick: () => { state.nextUi.editing = false; rerender(); } }, `← ${t("back")}`)) : null));
}

// ---------------------------------------------------------------- shared page head
function pageHead(title, sub) {
  const country = state.next.country;
  return h("section", { class: "page-head" }, h("div", { class: "container" },
    h("h1", {}, title), h("p", {}, sub),
    h("div", { class: "summary-bar" },
      h("div", { class: "seg nx-mode", role: "group", "aria-label": t("nx_q1") }, ["study", "work"].map((m) =>
        h("button", { type: "button", "aria-pressed": String(state.next.mode === m), onclick: () => switchMode(m) }, icon(m === "study" ? "grad" : "briefcase"), t(`nx_${m}`)))),
      h("span", { class: "based" }, country === "REMOTE" ? icon("globe") : flag(country), " ", countryName(country), " · ",
        h("a", { href: "#/next", onclick: (e) => { e.preventDefault(); state.nextUi.editing = true; rerender(); } }, t("nx_change"))))));
}

// ---------------------------------------------------------------- work
function sourceLink(j) {
  const feed = FEEDS[j.source];
  return feed ? ext(feed[1], feed[0]) : t("nx_careers");
}

function jobCard(j) {
  const ours = new Set((state.courses || []).map((c) => c.skill));
  const band = j.fit == null ? "" : j.fit >= 70 ? "ready" : j.fit >= 45 ? "close" : "stretch";
  const remote = j.remote === "WORLD" ? t("nx_remote_world") : j.remote ? t("nx_remote_badge") : null;
  return h("article", { class: "job-card" },
    h("div", { class: "job-top" },
      j.fit != null ? h("span", { class: `fit ${band}` }, t("nx_fit", { n: j.fit })) : null,
      j.level ? h("span", { class: "badge muted-badge" }, t(`nx_level_${j.level}`)) : null,
      remote ? h("span", { class: "badge remote" }, remote) : null,
      h("span", { class: "spacer" }),
      h("span", { class: "tiny muted" }, posted(j.posted))),
    h("h3", {}, ext(j.url, j.title)),
    h("p", { class: "job-meta" }, [j.company, j.location].filter(Boolean).join(" · ")),
    requirements(j),
    j.have.length ? h("div", { class: "row job-skills" }, h("span", { class: "k" }, t("nx_have")),
      j.have.map((s) => h("span", { class: "pill have", title: s.certified ? t("nx_cert_tip") : null }, "✓ ", skillShort(s.id), s.certified ? icon("award") : null))) : null,
    j.missing.length ? h("div", { class: "row job-skills" }, h("span", { class: "k" }, t("nx_learn")),
      j.missing.map((m) => (ours.has(m.id)
        ? h("a", { class: "pill learn", href: `#/learn/${m.id}` }, `${skillShort(m.id)} · ${m.hours} h →`)
        : h("span", { class: "pill" }, `${skillShort(m.id)} · ${m.hours} h`)))) : null,
    state.jobAdvice?.[j.id]?.off ? h("div", { class: "job-ai off" }, h("p", {}, t("nx_ai_off_job")))
      : state.jobAdvice?.[j.id] ? h("div", { class: "job-ai" }, h("p", {}, state.jobAdvice[j.id].text),
        h("p", { class: "tiny muted" }, t("nx_ai_note", { model: state.jobAdvice[j.id].model }), aiSource(state.jobAdvice[j.id].source))) : null,
    h("div", { class: "job-actions" },
      h("a", { class: "btn btn-primary btn-sm", href: j.url, target: "_blank", rel: "noopener" }, `${t("nx_apply")} ↗`),
      j.fit != null && !state.jobAdvice?.[j.id]                 // always offered; answered live, from a saved answer, or "AI is off"
        ? h("button", { type: "button", class: "btn btn-secondary btn-sm", onclick: (e) => askAI(j, e.currentTarget) }, icon("sparkles"), t("nx_ask_ai")) : null,
      h("span", { class: "tiny muted" }, `${t("nx_via")} `, sourceLink(j))));
}

function viewJobs() {
  const d = state.nextJobs;
  const ui = state.nextUi;
  const country = state.next.country;
  const anywhere = country === "REMOTE";
  const tab = anywhere ? "remote" : ui.tab;
  const list = d[tab];
  const total = d.counts[tab];
  const dirs = directions();
  const filters = h("div", { class: "nx-filters" },
    anywhere ? null : h("div", { class: "seg-tabs", role: "group" }, [["local", t("nx_tab_local", { country: inCountry(country) })], ["remote", t("nx_tab_remote")]].map(([id, label]) =>
      h("button", { type: "button", class: tab === id ? "on" : "", "aria-pressed": String(tab === id), onclick: () => { state.nextUi.tab = id; rerender(); } },
        label, h("span", { class: "n" }, d.counts[id].toLocaleString())))),
    h("div", { class: "seg", role: "group" }, LEVELS.map((lv) => h("button", { type: "button", "aria-pressed": String(ui.level === lv),
      onclick: () => { state.nextUi.level = lv; rerender(); } }, t(`nx_lv_${lv}`)))));
  const roleChips = dirs.length > 1 ? h("div", { class: "chips nx-roles" }, [["all", t("nx_all_roles")], ...dirs.map((r) => [r, roleTitle(r)])].map(([id, label]) => {
    const on = id === "all" ? !dirs.includes(ui.role) : ui.role === id;
    return h("button", { type: "button", class: `chip ${on ? "on" : ""}`, "aria-pressed": String(on), onclick: () => { state.nextUi.role = id; rerender(); } }, label);
  })) : null;
  const groups = d.scored
    ? [["nx_ready", (j) => j.fit >= 70], ["nx_close", (j) => j.fit >= 45 && j.fit < 70], ["nx_stretch", (j) => j.fit < 45]]
    : [["nx_newest", () => true]];
  const results = list.length
    ? groups.map(([key, test]) => {
      const items = list.filter(test);
      return items.length ? [h("h3", { class: "nx-group" }, t(key), h("span", { class: "n" }, String(items.length))), items.map(jobCard)] : null;
    })
    : h("div", { class: "notice info", style: { marginTop: "20px" } }, t("nx_none"));
  const certs = Object.entries(state.certs);
  const side = h("div", { class: "stack" },
    d.portals.length ? h("div", { class: "card" }, h("h3", {}, t("nx_portals_t")),
      h("p", { class: "small muted", style: { marginTop: "4px" } }, anywhere ? t("nx_portals_d_remote", { role: d.search_title }) : t("nx_portals_d", { role: d.search_title, country: inCountry(country) })),
      h("div", { class: "portal-list" }, d.portals.map((p) => h("a", { class: "portal", href: p.url, target: "_blank", rel: "noopener" },
        h("span", {}, p.name), p.official ? h("span", { class: "badge robust" }, t("nx_official")) : null, h("span", { class: "go", "aria-hidden": "true" }, "↗"))))) : null,
    h("div", { class: "card" }, h("h3", {}, t("nx_certs_t")),
      certs.length
        ? [h("p", { class: "small muted", style: { marginTop: "4px" } }, t("nx_certs_d")),
          h("div", { class: "row", style: { marginTop: "12px" } }, certs.map(([sid, c]) => h("a", { class: "pill have", href: `#/certificate/${c.token}` }, icon("award"), skillShort(sid))))]
        : [h("p", { class: "small muted", style: { marginTop: "4px" } }, t("nx_certs_none")),
          h("a", { class: "btn btn-secondary btn-sm", href: "#/learn", style: { marginTop: "12px" } }, icon("book"), t("nav_learn"))]));
  return h("div", {},
    pageHead(anywhere ? t("nx_jobs_h_remote") : t("nx_jobs_h", { country: inCountry(country) }), t("nx_jobs_sub")),
    h("section", { class: "band", style: { paddingTop: "28px" } }, h("div", { class: "container grid-main" },
      h("div", {},
        filters, roleChips,
        d.scored ? aboutYou() : null,
        d.scored ? marketPanel() : null,
        d.scored ? null : h("div", { class: "notice info", style: { marginTop: "18px" } }, h("div", {},
          h("p", {}, t("nx_no_profile")), h("a", { class: "btn btn-primary btn-sm", href: "#/start?step=1", style: { marginTop: "10px" } }, t("hero_start")))),
        results,
        total > list.length ? h("p", { class: "small muted", style: { marginTop: "14px" } }, t("nx_showing", { n: list.length, total: total.toLocaleString() })) : null,
        h("p", { class: "source-line" }, t("nx_jobs_src", { n: d.total.toLocaleString(), date: dateLabel(d.updated) }), " ",
          `${t("nx_sources")} `, [...Object.values(FEEDS).map(([name, url]) => ext(url, name)), t("nx_boards")].map((x, i) => [i ? ", " : "", x]), ".")),
      side)));
}

// ---------------------------------------------------------------- study
function uniRow(u, i, field) {
  const host = hostOf(u.site);
  const query = host ? `site:${host} ${field.search}` : `${u.name} ${field.search}`;
  return h("li", { class: "uni" },
    h("span", { class: "uni-n" }, String(i + 1)),
    h("div", { class: "uni-body" }, h("b", {}, u.name),
      h("div", { class: "tiny muted" }, [host, u.known ? t("nx_known", { n: u.known }) : null].filter(Boolean).join(" · "))),
    h("div", { class: "uni-actions" },
      h("a", { class: "btn btn-secondary btn-sm", href: `https://www.google.com/search?q=${encodeURIComponent(query)}`, target: "_blank", rel: "noopener",
        title: t("nx_find_prog_tip", { uni: u.name, field: loc(field.label) }) }, `${t("nx_find_prog")} ↗`),
      u.site ? h("a", { class: "btn btn-link", href: u.site, target: "_blank", rel: "noopener" }, `${t("nx_website")} ↗`) : null));
}

function viewStudy() {
  const d = state.nextStudy;
  const ui = state.nextUi;
  const country = state.next.country;
  const fieldId = d.fields[ui.field] ? ui.field : d.recommended[0];
  const field = d.fields[fieldId];
  const fieldIds = ui.allFields ? [...d.recommended, ...Object.keys(d.fields).filter((id) => !d.recommended.includes(id))] : d.recommended;
  const fields = h("div", { class: "card" },
    h("h3", {}, t("nx_fields_t")), h("p", { class: "small muted", style: { marginTop: "4px" } }, t("nx_fields_d")),
    h("div", { class: "chips", style: { marginTop: "14px" } }, fieldIds.map((id) => h("button", { type: "button", class: `chip ${id === fieldId ? "on" : ""}`,
      "aria-pressed": String(id === fieldId), onclick: () => { state.nextUi.field = id; rerender(); } }, loc(d.fields[id].label))),
    h("button", { type: "button", class: "btn btn-link", onclick: () => { state.nextUi.allFields = !ui.allFields; rerender(); } }, t(ui.allFields ? "nx_fewer_fields" : "nx_more_fields"))));
  // the university search filters in place, so typing never loses focus
  const listBox = h("div", {});
  const fillList = () => {
    const q = fold(ui.uniQ.trim());
    const unis = q ? d.universities.filter((u) => fold(u.name).includes(q)) : d.universities;
    const shown = unis.slice(0, ui.uniShown);
    listBox.replaceChildren(
      unis.length ? h("ol", { class: "uni-list" }, shown.map((u) => uniRow(u, d.universities.indexOf(u), field)))
        : h("p", { class: "small muted", style: { marginTop: "14px" } }, t("nx_no_unis", { q: ui.uniQ })),
      h("div", { class: "row", style: { marginTop: "14px", justifyContent: "space-between" } },
        h("span", { class: "small muted" }, t("nx_unis_count", { n: shown.length, total: unis.length })),
        shown.length < unis.length ? h("button", { type: "button", class: "btn btn-secondary btn-sm", onclick: () => { ui.uniShown += 20; fillList(); } }, t("nx_show_more")) : null));
  };
  fillList();
  const search = h("div", { class: "search compact nx-uni-search" }, icon("search"),
    h("input", { type: "search", placeholder: t("nx_uni_search"), "aria-label": t("nx_uni_search"), value: ui.uniQ,
      oninput: (e) => { ui.uniQ = e.target.value; ui.uniShown = 20; fillList(); } }));
  const links = (items) => h("ul", { class: "link-list" }, items.map((x) => h("li", {}, ext(x.url, x.name, "\u00a0↗"))));
  const prepare = field.prepare.map((sid) => state.courses?.find((c) => c.skill === sid)).filter(Boolean);
  const side = h("div", { class: "stack" },
    h("div", { class: "card" }, h("h3", {}, t("nx_apply_t")), d.apply.length ? links(d.apply) : h("p", { class: "small muted", style: { marginTop: "6px" } }, t("nx_apply_none"))),
    h("div", { class: "card" }, h("h3", {}, t("nx_fund_t")), d.funding.length ? links(d.funding) : null,
      h("p", { class: "small muted", style: { marginTop: "10px" } }, t(d.funding.length ? "nx_fund_more" : "nx_fund_none"))),
    prepare.length ? h("div", { class: "card" }, h("h3", {}, t("nx_prep_t")), h("p", { class: "small muted", style: { marginTop: "4px" } }, t("nx_prep_d", { field: loc(field.label) })),
      prepare.map((c) => h("a", { class: "prep", href: `#/learn/${c.skill}` }, h("b", {}, c.title),
        h("span", { class: "tiny muted" }, [t("lessons_n", { n: c.lessons }), hoursLabel(c.minutes), state.certs[c.skill] ? t("certified") : t("chip_cert")].join(" · "))))) : null,
    h("div", { class: "card" }, h("h3", {}, t("nx_rank_t")), h("p", { class: "small muted", style: { marginTop: "4px" } }, t("nx_rank_d")), links(d.rankings)));
  return h("div", {},
    pageHead(t("nx_study_h", { country: inCountry(country) }), t("nx_study_sub")),
    h("section", { class: "band", style: { paddingTop: "28px" } }, h("div", { class: "container grid-main" },
      h("div", {}, fields, h("div", { class: "row", style: { marginTop: "24px" } }, search), listBox,
        h("p", { class: "source-line" }, d.total > d.universities.length ? `${t("nx_unis_more", { n: d.universities.length, total: d.total.toLocaleString() })} ` : "",
          t("nx_unis_src", { date: dateLabel(d.updated) }))),
      side)));
}

// ---------------------------------------------------------------- links in from other pages
export function nextCta() {
  return h("div", { class: "card next-cta" },
    h("span", { class: "icon-circle" }, icon("briefcase")),
    h("div", { class: "nc-body" }, h("h3", {}, t("nx_cta_t")), h("p", { class: "small muted" }, t("nx_cta_d"))),
    h("a", { class: "btn btn-primary", href: "#/next" }, `${t("nx_cta_btn")} →`));
}
