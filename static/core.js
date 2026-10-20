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
  courses: null, course: null, lesson: null, outlineOpen: false, quiz: { sid: null, data: null, answers: [], idx: 0, result: null, name: "", busy: false },
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
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zm0-14v5l3 2", check: "M5 12.5l4.5 4.5L19 7.5", play: "M8 5.5v13l10.5-6.5z",
  list: "M9 6h12M9 12h12M9 18h12M4 6h.01M4 12h.01M4 18h.01", code: "M8 8l-5 4 5 4M16 8l5 4-5 4M14 4l-4 16", chevron: "M6 9l6 6 6-6",
  close: "M6 6l12 12M18 6L6 18", layers: "M12 3l9 5-9 5-9-5 9-5zM3 12l9 5 9-5M3 16.5l9 5 9-5", arrowLeft: "M19 12H5m6-6-6 6 6 6",
  shield: "M12 3l8 3v6c0 4.6-3.4 8.1-8 9-4.6-.9-8-4.4-8-9V6l8-3zm-3.5 9 2.5 2.5 4.5-4.5",
  // course cover icons
  database: "M12 3c4.4 0 8 1.3 8 3s-3.6 3-8 3-8-1.3-8-3 3.6-3 8-3zM4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6",
  sigma: "M18 4H6l6 8-6 8h12", pie: "M12 3v9h9a9 9 0 1 1-9-9zm3 .5A9 9 0 0 1 20.5 9H15z",
  sparkles: "M12 3l1.8 4.7 4.7 1.8-4.7 1.8L12 16l-1.8-4.7-4.7-1.8 4.7-1.8zM19 15l.8 2.2 2.2.8-2.2.8L19 21l-.8-2.2-2.2-.8 2.2-.8z",
  message: "M4 5h16v11H9l-5 4V5zm4 5h8M8 13h5", rocket: "M14 4c3-1 6-1 6-1s0 3-1 6l-6 6-5-5 6-6zM9 10l-4 1 3 3M14 15l-1 4-3-3M6 15c-1.5 1.5-2 4-2 5 1 0 3.5-.5 5-2",
  flow: "M4 5h6v5H4zM14 14h6v5h-6zM7 10v3a2 2 0 0 0 2 2h5", eye: "M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12zm10 3a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  grid: "M4 4h16v16H4zM4 10h16M4 16h16M10 4v16", globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3 12h18M12 3c2.5 2.5 3.5 5.5 3.5 9s-1 6.5-3.5 9c-2.5-2.5-3.5-5.5-3.5-9s1-6.5 3.5-9z",
  layout: "M4 4h16v16H4zM4 9h16M9 9v11", cloud: "M7 18h10a4 4 0 0 0 .5-8A6 6 0 0 0 6 9.5 4.3 4.3 0 0 0 7 18z",
  terminal: "M4 5h16v14H4zM7 9l3 3-3 3M12 15h5", lock: "M6 11h12v9H6zM8 11V7a4 4 0 0 1 8 0v4",
  bot: "M7 8h10a3 3 0 0 1 3 3v6a3 3 0 0 1-3 3H7a3 3 0 0 1-3-3v-6a3 3 0 0 1 3-3zM12 4v4M9 13h.01M15 13h.01",
  wifi: "M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0M12 19.5h.01M2 9a14 14 0 0 1 20 0", megaphone: "M3 11v2l13 5V6zM16 9a3 3 0 0 1 0 6M6 13l1 6h3l-1-5",
  sun: "M12 17a5 5 0 1 0 0-10 5 5 0 0 0 0 10zM12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4",
  bolt: "M13 2L4 14h7l-1 8 9-12h-7z", file: "M6 3h9l4 4v14H6zM14 3v5h5M9 13h7M9 17h7", factory: "M3 21V10l6 4v-4l6 4V6l6 4v11zM7 17h2M12 17h2M17 17h2",
  car: "M5 16h14l-2-6H7zM5 16v3M19 16v3M7 10l1.5-4h7L17 10M8 13h.01M16 13h.01", map: "M9 4l6 3 6-3v13l-6 3-6-3-6 3V7zM9 4v13M15 7v13",
  refresh: "M20 11a8 8 0 0 0-14.9-3M4 4v4h4M4 13a8 8 0 0 0 14.9 3M20 20v-4h-4", plug: "M9 2v6M15 2v6M6 8h12v4a6 6 0 0 1-12 0zM12 18v4",
  chat: "M21 12a8 8 0 0 1-11.8 7L4 20l1-5A8 8 0 1 1 21 12z", headset: "M4 14v-2a8 8 0 0 1 16 0v2M4 14h3v5H5a1 1 0 0 1-1-1zM20 14h-3v5h2a1 1 0 0 0 1-1z",
  clipboard: "M9 3h6v3H9zM7 4.5H5V21h14V4.5h-2M9 13l2 2 4-4", bulb: "M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.7.7 1 1.5 1 2.5h6c0-1 .3-1.8 1-2.5A6 6 0 0 0 12 3z",
  grad: "M2 9l10-5 10 5-10 5zM6 11v5c3 2 9 2 12 0v-5M22 9v6", calc: "M6 3h12v18H6zM9 7h6M9 11h.01M12 11h.01M15 11h.01M9 15h.01M12 15h.01M15 15h.01M9 18h6",
  keyboard: "M3 7h18v10H3zM7 10h.01M11 10h.01M15 10h.01M7 14h10", palette: "M12 21a9 9 0 1 1 9-9c0 2-1.5 3-3 3h-2a2 2 0 0 0-1 3.7A2 2 0 0 1 12 21zM7.5 11h.01M10.5 7h.01M15 7.5h.01",
  bookOpen: "M12 6c-2-2-5-2-9-1v14c4-1 7-1 9 1 2-2 5-2 9-1V5c-4-1-7-1-9 1zM12 6v14",
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
