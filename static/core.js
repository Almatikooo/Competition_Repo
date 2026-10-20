// Shared state and helpers for all Path.AI views.
import { h } from "./charts.js";
import { makeT } from "./i18n.js";

export const store = {
  get(key, fallback) { try { const v = localStorage.getItem(`pathai:${key}`); return v ? JSON.parse(v) : fallback; } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(`pathai:${key}`, JSON.stringify(value)); } catch { /* private mode */ } },
};

export const EMPTY_PROFILE = { skills: {}, interests: [], sdg_priorities: [], current_role: null, hours_per_week: 6 };

export const state = {
  meta: null, personas: [],
  lang: store.get("lang", "en"), scenario: "moderate", asOf: null,
  profile: store.get("profile", structuredClone(EMPTY_PROFILE)), origin: store.get("origin", null), tiles: store.get("tiles", []),
  wizard: { step: 1, query: "", student: false, busy: false, skillQuery: "", searchOpen: false, cvNote: null },
  weights: { fit: 0.5, outlook: 0.3, preference: 0.2 },
  matches: null, matchesKey: "", expanded: {}, showMore: false, explanations: {},
  pathway: null, pathwayKey: "", openOpts: {}, progress: store.get("progress", {}),
  radar: null, radarKey: "", radarView: "radar", skillDetail: null, team: null, teamKey: "", busy: false,
  // Learn
  courses: null, course: null, step: 0, quiz: { answers: [], result: null, name: "", busy: false },
  learned: store.get("learned", {}), certs: store.get("certs", {}), learnFilter: { cat: "all", q: "" },
  certView: null, certViewToken: null,
};

let table = makeT(state.lang);
export const t = (key, vars) => table(key, vars);

export function setLang(code) {
  state.lang = code;
  store.set("lang", code);
  table = makeT(code);
  state.matchesKey = "";
  state.explanations = {};
}

export const $ = (id) => document.getElementById(id);

export async function api(path, body, isForm = false) {
  const opts = body ? { method: "POST", body: isForm ? body : JSON.stringify(body), headers: isForm ? {} : { "Content-Type": "application/json" } } : {};
  const resp = await fetch(path, opts);
  if (!resp.ok) {
    let detail = resp.statusText;
    try { detail = (await resp.json()).detail || detail; } catch { /* not json */ }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return resp.json();
}

let indexFor = null;
function index() {
  if (!indexFor || indexFor.meta !== state.meta) {
    indexFor = { meta: state.meta, skills: Object.fromEntries(state.meta.skills.map((x) => [x.id, x])), roles: Object.fromEntries(state.meta.roles.map((x) => [x.id, x])) };
  }
  return indexFor;
}
export const skillById = () => index().skills;
export const roleById = () => index().roles;
export const loc = (obj) => (obj && (obj[state.lang] || obj.en)) || "";
export const skillName = (id) => loc(skillById()[id]?.name) || id;
export const skillShort = (id) => (state.lang === "en" && skillById()[id]?.short) || skillName(id);
export const roleTitle = (id) => loc(roleById()[id]?.title) || id;
export const goalOf = (n) => state.meta.sdg_goals.find((g) => g.goal === n);
export const hasProfile = () => Object.keys(state.profile.skills).length > 0;

const LOCALES = { en: "en-MY", ms: "ms-MY", zh: "zh-CN" };
export const dateLabel = (iso, lang = state.lang) => (iso ? new Date(iso).toLocaleDateString(LOCALES[lang], { day: "numeric", month: "short", year: "numeric" }) : "–");
export const monthLabel = (m) => (m ? new Date(`${m}-01T00:00:00`).toLocaleDateString(LOCALES[state.lang], { month: "short", year: "numeric" }) : "–");

let renderFn = () => {};
export function setRenderer(fn) { renderFn = fn; }
export function rerender() { return renderFn(); }
export const go = (hash) => { if (location.hash === hash) rerender(); else location.hash = hash; };

export function toast(msg) {
  const el = h("div", { class: "toast", role: "status" }, msg);
  document.body.append(el);
  setTimeout(() => el.remove(), 2800);
}

export function saveProfile() {
  store.set("profile", state.profile);
  store.set("origin", state.origin);
  store.set("tiles", state.tiles);
  state.matchesKey = "";
  state.pathwayKey = "";
  state.explanations = {};
}

export function sdgBadge(goal, small = true, title) {
  const g = goalOf(goal);
  return h("span", { class: `sdg-badge ${small ? "sm" : ""}`, style: { background: g.color }, title: title || `SDG ${goal}: ${loc(g.name)}` }, String(goal));
}

export function costTag(cost) {
  return h("span", { class: `cost ${cost === "free" ? "free" : ""}` }, t(`cost_${cost}`));
}

const ICONS = {
  trend: "M3 17l6-6 4 4 8-8M15 7h6v6", target: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zm0-5a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm0-3a1 1 0 1 0 0-2",
  route: "M6 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4zm12-10a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM6 15V9a4 4 0 0 1 4-4h4M18 9v6a4 4 0 0 1-4 4h-4",
  search: "M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zm10 2-4.35-4.35",
  cpu: "M9 3v2M15 3v2M9 19v2M15 19v2M3 9h2M3 15h2M19 9h2M19 15h2M7 5h10a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zm3 5h4v4h-4z",
  chart: "M4 20V10M10 20V4M16 20v-7M22 20H2", leaf: "M5 21c0-9 6-15 16-16-1 10-7 16-16 16zm0 0 8-8",
  sprout: "M12 21v-9M12 12C12 8 9 5 4 5c0 4 3 7 8 7zm0 0c0-3 2-6 7-6 0 3-2 6-7 6", heart: "M12 21s-8-5.5-8-11a4.5 4.5 0 0 1 8-2.8A4.5 4.5 0 0 1 20 10c0 5.5-8 11-8 11z",
  briefcase: "M4 8h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1zm5 0V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3M3 13h18",
  users: "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-7 10v-1a6 6 0 0 1 12 0v1M16 3.5a4 4 0 0 1 0 7M22 21v-1a6 6 0 0 0-4-5.6",
  pen: "M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4", upload: "M12 16V4M7 9l5-5 5 5M4 20h16",
  book: "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5zm0 16a2 2 0 0 1 2-2h13", award: "M12 15a6 6 0 1 0 0-12 6 6 0 0 0 0 12zm-3.5-1L7 22l5-3 5 3-1.5-8",
};
export function icon(name) {
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  for (const [k, v] of Object.entries({ viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "2", "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" })) svg.setAttribute(k, v);
  const path = document.createElementNS(NS, "path");
  path.setAttribute("d", ICONS[name]);
  svg.append(path);
  return svg;
}

export async function ensureRadar() {
  const key = `${state.asOf}|${state.scenario}`;
  if (state.radarKey === key) return;
  state.radar = await api("/api/radar", { as_of: state.asOf, scenario: state.scenario });
  state.radarKey = key;
}

export async function ensureMatches() {
  const key = JSON.stringify([state.asOf, state.scenario, state.lang, state.profile, state.weights]);
  if (state.matchesKey === key) return;
  state.matches = await api("/api/match", { as_of: state.asOf, scenario: state.scenario, lang: state.lang, profile: state.profile, weights: state.weights });
  state.matchesKey = key;
}

export async function ensureCourses() {
  if (!state.courses) state.courses = (await api("/api/learn/courses")).courses;
}
