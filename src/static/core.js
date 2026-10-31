// Shared state and helpers for all Path.AI views.
import { h } from "./charts.js";
import { makeT } from "./i18n.js";

// Guests keep their progress in this tab only, so it is gone when the tab is closed (sessionStorage). A person signed
// in with Google also has the same keys saved to their account (see `account`), and they come back on any device.
// The interface language and the achievement sound are preferences of the device, kept across visits (localStorage).
const DEVICE_KEYS = new Set(["lang", "sound"]);
const SYNCED = new Set(["profile", "origin", "tiles", "progress", "learned", "certs", "certName", "coach", "next", "focusRole", "activity", "goal", "path",
  "badges", "tally", "rewards"]);
const area = (key) => (DEVICE_KEYS.has(key) ? localStorage : sessionStorage);
// The answers a guest just gave in the wizard. Signing in from its last step ("save your results") keeps them.
const ANSWERS = ["profile", "origin", "tiles"];
const KEEP_ANSWERS = "pathai-ui:keep-answers";
export function keepAnswersOnSignIn() { try { sessionStorage.setItem(KEEP_ANSWERS, "1"); } catch { /* storage blocked */ } }

export const account = {
  user: null, providers: {}, pending: {}, timer: null,
  changed(key, value) {
    if (!this.user || !SYNCED.has(key)) return;
    this.pending[key] = value;
    clearTimeout(this.timer);
    this.timer = setTimeout(() => this.flush(), 1200);
  },
  async flush(keepalive = false) {
    const batch = this.pending;
    this.pending = {};
    if (!Object.keys(batch).length) return;
    try {
      const r = await fetch("/api/me/state", { method: "PUT", keepalive, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ state: batch }) });
      if (!r.ok && r.status !== 422) throw new Error(r.statusText);
    } catch { this.pending = { ...batch, ...this.pending }; }    // sent again with the next change
  },
};
addEventListener("pagehide", () => account.flush(true));

export const store = {
  get(key, fallback) { try { const v = area(key).getItem(`pathai:${key}`); return v ? JSON.parse(v) : fallback; } catch { return fallback; } },
  set(key, value) {
    try { area(key).setItem(`pathai:${key}`, JSON.stringify(value)); } catch { /* storage blocked */ }
    account.changed(key, value);
  },
};

// Before accounts existed, progress was kept in localStorage for good: move it into this tab's storage, once.
try {
  for (const k of Object.keys(localStorage)) {
    if (!k.startsWith("pathai:") || DEVICE_KEYS.has(k.slice(7))) continue;
    if (sessionStorage.getItem(k) === null) sessionStorage.setItem(k, localStorage.getItem(k));
    localStorage.removeItem(k);
  }
} catch { /* storage blocked */ }

export const DEFAULT_LANGUAGES = ["en", "ms"];   // most Malaysian users work in English and Malay; one tap changes it
export const EMPTY_PROFILE = { skills: {}, interests: [], sdg_priorities: [], current_role: null, hours_per_week: 6, years_experience: null, languages: DEFAULT_LANGUAGES };

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
  courses: null, course: null, lesson: null, outlineOpen: false, quiz: { key: null, part: null, data: null, answers: [], idx: 0, result: null, error: null, locked: false, name: "", busy: false },
  learned: store.get("learned", {}), certs: store.get("certs", {}), learnFilter: { cat: "all", q: "" },
  certView: null, certViewToken: null,
  // Opportunities
  next: store.get("next", { mode: null, country: null }), nextMeta: null, nextJobs: null, nextJobsKey: "", nextStudy: null, nextStudyKey: "",
  // My path: the job worked towards, its steps and readiness by day, and what was done each day (visits, lessons, tests)
  goal: store.get("goal", null), path: store.get("path", {}), activity: store.get("activity", {}), pathCourse: null, streakOpen: false,
  // Achievements: when each was unlocked, and what was done along the way that they count (see badges.js)
  badges: store.get("badges", {}), tally: store.get("tally", {}), badgeSel: null, scrollTo: null, openDetails: {},
  // Rewards: gifts claimed with the points the achievements earn (see rewards.js)
  rewards: store.get("rewards", []), rewardsUi: { cat: "all", reach: false },
  nextUi: { editing: false, q: "", tab: "local", level: "any", role: "all", field: null, allFields: false, uniQ: "", uniShown: 20 },
};

let table = makeT(state.lang);

// Re-reads the saved keys into the state (after signing in: the account's progress replaces this tab's).
export function hydrate() {
  Object.assign(state, { profile: store.get("profile", structuredClone(EMPTY_PROFILE)), origin: store.get("origin", null), tiles: store.get("tiles", []),
    progress: store.get("progress", {}), learned: store.get("learned", {}), certs: store.get("certs", {}), next: store.get("next", { mode: null, country: null }),
    goal: store.get("goal", null), path: store.get("path", {}), activity: store.get("activity", {}),
    badges: store.get("badges", {}), tally: store.get("tally", {}), rewards: store.get("rewards", []),
    coach: null, matchesKey: "", pathwayKey: "", nextJobsKey: "", nextStudyKey: "" });
}

// On every page load: who is signed in. The account's saved progress wins; a first sign-in keeps what this tab has.
// Signing in from the wizard's save step keeps the answers just given, plus anything in this tab the account lacks.
export async function startAccount() {
  let me, keep = false;
  try { keep = sessionStorage.getItem(KEEP_ANSWERS) === "1"; sessionStorage.removeItem(KEEP_ANSWERS); } catch { /* storage blocked */ }
  try { me = await api("/api/me"); } catch { return; }
  account.providers = me.providers || {};
  if (!me.user) return;
  account.user = me.user;
  const saved = Object.fromEntries(Object.entries(me.state || {}).filter(([k]) => SYNCED.has(k)));
  const first = !Object.keys(saved).length;
  const here = (k) => store.get(k, undefined) !== undefined;
  const upload = first ? [...SYNCED] : keep ? [...SYNCED].filter((k) => ANSWERS.includes(k) || !(k in saved)) : [];
  for (const [k, v] of Object.entries(saved)) {
    if (upload.includes(k) && here(k)) continue;           // the answers just given win
    try { sessionStorage.setItem(`pathai:${k}`, JSON.stringify(v)); } catch { /* storage blocked */ }
  }
  for (const k of upload) if (here(k)) account.pending[k] = store.get(k, undefined);
  if (!first) hydrate();
  await account.flush();
}

function forgetThisTab() {
  try { for (const k of Object.keys(sessionStorage)) if (/^pathai(:|-ui:)/.test(k)) sessionStorage.removeItem(k); } catch { /* storage blocked */ }
}

export async function signOut() {
  await account.flush();
  await api("/auth/logout", {});
  forgetThisTab();                       // the next person on this device starts fresh
  location.hash = "#/";
  location.reload();
}

export async function deleteAccount() {
  await api("/api/me", null, false, "DELETE");
  forgetThisTab();
  location.hash = "#/";
  location.reload();
}
export const t = (key, vars) => table(key, vars);

export function setLang(code) {
  state.lang = code;
  store.set("lang", code);
  table = makeT(code);
  state.matchesKey = "";
  state.explanations = {};
}

export const $ = (id) => document.getElementById(id);

export async function api(path, body, isForm = false, method = null) {
  const opts = body ? { method: method || "POST", body: isForm ? body : JSON.stringify(body), headers: isForm ? {} : { "Content-Type": "application/json" } }
    : method ? { method } : {};
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
export const timeLabel = (iso, lang = state.lang) => (iso ? new Date(iso).toLocaleTimeString(LOCALES[lang], { hour: "2-digit", minute: "2-digit" }) : "–");
export const monthLabel = (m) => (m ? new Date(`${m}-01T00:00:00`).toLocaleDateString(LOCALES[state.lang], { month: "short", year: "numeric" }) : "–");

let renderFn = () => {};
export function setRenderer(fn) { renderFn = fn; }
export function rerender() { return renderFn(); }
export const go = (hash) => { if (location.hash === hash) rerender(); else location.hash = hash; };

// A <details> that stays the way the person left it when the page is drawn again (e.g. after a slider moves): open
// until they close it themselves.
export const keepOpen = (key) => ({ open: !!state.openDetails[key],
  ontoggle: (e) => { state.openDetails = { ...state.openDetails, [key]: e.currentTarget.open }; } });

// Where an AI answer came from: written just now by our model on our GPU (RunPod), by the hosted backup copy of the
// same model, or saved earlier (the example people's answers, shown while our GPU is off).
export function aiSource(src) {
  return ["gpu", "backup", "saved"].includes(src) ? h("span", { class: `ai-src ${src}` }, h("i"), t(`ai_src_${src}`)) : null;
}

export function toast(msg) {
  const el = h("div", { class: "toast", role: "status" }, msg);
  document.body.append(el);
  setTimeout(() => el.remove(), 2800);
}

// A passed final test proves the skill: it shows as Advanced in the profile (a level is never lowered).
export function masterSkill(sid) {
  if (!hasProfile() || (state.profile.skills[sid] || 0) >= 3) return false;
  state.profile.skills = { ...state.profile.skills, [sid]: 3 };
  saveProfile();
  return true;
}

// ---------------------------------------------------------------- days, activity and the streak
// Days are the person's local calendar days ("2026-10-29").
export const dayKey = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
export const shiftDay = (key, n) => { const [y, m, d] = key.split("-").map(Number); return dayKey(new Date(y, m - 1, d + n)); };

// What was done each day: v visited, l lessons finished, t tests passed, m minutes of lessons. Kept for 400 days.
export function logActivity(kind, n = 1, minutes = 0) {
  const today = dayKey();
  const was = state.activity[today] || {};
  if (kind === "v" && was.v) return false;
  const day = { ...was, v: 1 };
  if (kind !== "v") day[kind] = (day[kind] || 0) + n;
  if (minutes) day.m = (day.m || 0) + Math.round(minutes);
  const keep = shiftDay(today, -400);
  state.activity = Object.fromEntries(Object.entries({ ...state.activity, [today]: day }).filter(([d]) => d >= keep).sort(([a], [b]) => (a < b ? -1 : 1)));
  store.set("activity", state.activity);
  return true;
}

// The visit streak: days visited in a row, where one missed day in between is forgiven and two in a row end it.
// `ended` is the length of the streak that ended just before a new one started today (0 otherwise).
export function streak(activity = state.activity, today = dayKey()) {
  const runs = [];
  for (const d of Object.keys(activity || {}).filter((k) => activity[k]?.v && k <= today).sort()) {
    const run = runs[runs.length - 1];
    if (run && d <= shiftDay(run.end, 2)) Object.assign(run, { count: run.count + 1, end: d });
    else runs.push({ count: 1, end: d });
  }
  const last = runs[runs.length - 1];
  const alive = !!last && last.end >= shiftDay(today, -2);
  const before = runs[runs.length - (alive ? 2 : 1)];
  return { count: alive ? last.count : 0, best: Math.max(0, ...runs.map((r) => r.count)),
    ended: alive && last.count === 1 && before ? before.count : 0 };
}

// ---------------------------------------------------------------- what the achievements count
// Numbers add up (questions asked in the AI chat…) or keep the highest value seen (steps of the path done…); lists keep
// distinct values (pages opened, languages used, countries searched…).
function setTally(key, value) {
  state.tally = { ...state.tally, [key]: value };
  store.set("tally", state.tally);
}
export const bump = (key, n = 1) => setTally(key, (state.tally[key] || 0) + n);
export function noteMax(key, value) { if (value > (state.tally[key] || 0)) setTally(key, value); }
export function remember(key, value) {
  const list = state.tally[key] || [];
  if (value === null || value === undefined || list.includes(value)) return;
  setTally(key, [...list, value].slice(-100));
}

export function saveProfile() {
  store.set("profile", state.profile);
  store.set("origin", state.origin);
  store.set("tiles", state.tiles);
  state.matchesKey = "";
  state.pathwayKey = "";
  state.explanations = {};
}

// ---------------------------------------------------------------- UN goals
// Every goal badge is a button: it opens what the goal means, its official wording, the targets Path.AI links to
// and the jobs and skills that contribute. `ctx` ({ role } or { skill }) adds how that role or skill contributes.
// Contrast of white and of ink text on a goal colour (WCAG relative luminance).
function contrasts(hex) {
  const lin = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  const [r, g, b] = [1, 3, 5].map((i) => lin(parseInt(hex.slice(i, i + 2), 16) / 255));
  const L = 0.2126 * r + 0.7152 * g + 0.0722 * b;
  return { white: 1.05 / (L + 0.05), ink: (L + 0.05) / 0.0629 };
}
// Badges keep the UN's white numerals unless they would be hard to read (yellow, light orange, light blue, light green).
const headInk = (hex) => { const c = contrasts(hex); return c.white >= c.ink ? "#fff" : "#1e1e1e"; };

export function sdgBadge(goal, small = true, title, ctx = null) {
  const g = goalOf(goal);
  return h("button", { type: "button", class: `sdg-badge ${small ? "sm" : ""}`, style: { background: g.color }, title: title || `SDG ${goal}: ${loc(g.name)}`,
    "aria-label": t("sdg_open", { n: goal, name: loc(g.name) }), "aria-haspopup": "dialog",
    onclick: (e) => { e.preventDefault(); e.stopPropagation(); remember("sdgs", goal); openGoal(goal, ctx, e.currentTarget); } }, String(goal));
}

const targetOrder = (id) => { const [a, b] = id.split("."); return Number(a) * 1000 + (/^\d+$/.test(b) ? Number(b) : 500 + b.charCodeAt(0)); };

export function openGoal(goal, ctx = null, opener = null) {
  const g = goalOf(goal);
  const targetText = (id) => state.meta.sdg_targets_local?.[state.lang]?.[id] || state.meta.sdg_targets[id] || "";
  const roles = state.meta.roles.filter((r) => r.sdgs.some((x) => x.goal === goal))
    .sort((a, b) => (a.kind === "target" ? 0 : 1) - (b.kind === "target" ? 0 : 1) || loc(a.title).localeCompare(loc(b.title)));
  const skills = state.meta.skills.filter((x) => x.sdgs?.some((l) => l.goal === goal));
  const targets = [...new Set([...roles, ...skills].flatMap((x) => x.sdgs).filter((l) => l.goal === goal).map((l) => l.target))]
    .sort((a, b) => targetOrder(a) - targetOrder(b));
  const own = ctx?.role ? { title: roleTitle(ctx.role), links: roleById()[ctx.role]?.sdgs || [] }
    : ctx?.skill ? { title: skillName(ctx.skill), links: skillById()[ctx.skill]?.sdgs || [] } : null;
  const ownLinks = own ? own.links.filter((l) => l.goal === goal) : [];
  const capped = (items, render, max = 14) => [items.slice(0, max).map(render), items.length > max ? h("span", { class: "chip static" }, t("sdg_more", { n: items.length - max })) : null];
  let dlg;
  const close = () => dlg.close();
  dlg = h("dialog", { class: "sdg-dialog", "aria-labelledby": "sdg-dlg-title", onclick: (e) => { if (e.target === dlg) close(); },
    onclose: () => { dlg.remove(); if (opener?.isConnected) opener.focus(); } },
  h("div", { class: "sdg-dlg" },
    h("div", { class: "sdg-dlg-head", style: { "--goal": g.color, "--goal-ink": headInk(g.color) } },
      h("span", { class: "sdg-dlg-num" }, String(goal)),
      h("div", { class: "sdg-dlg-titles" }, h("div", { class: "sdg-dlg-kicker" }, t("sdg_kicker", { n: goal })), h("h2", { id: "sdg-dlg-title" }, loc(g.name))),
      h("button", { type: "button", class: "sdg-dlg-close", "aria-label": t("close"), onclick: close }, "✕")),
    h("div", { class: "sdg-dlg-body" },
      h("p", { class: "sdg-essence" }, loc(g.essence)),
      ownLinks.length ? h("div", { class: "sdg-own", style: { "--goal": g.color } }, h("h3", {}, t("sdg_here", { what: own.title })),
        ownLinks.map((l) => h("p", {}, h("b", {}, `${l.target} `), l.why))) : null,
      h("div", { class: "sdg-official" }, h("div", { class: "k" }, t("sdg_official")), h("p", {}, loc(g.statement))),
      targets.length ? [h("h3", {}, t("sdg_targets")), h("ul", { class: "sdg-targets" }, targets.map((id) => h("li", {}, h("b", {}, id), h("span", {}, targetText(id)))))] : null,
      roles.length ? [h("h3", {}, t("sdg_jobs")), h("div", { class: "chips" }, capped(roles, (r) => (r.kind === "target"
        ? h("a", { class: "chip", href: `#/plan/${r.id}`, onclick: close }, loc(r.title)) : h("span", { class: "chip static" }, loc(r.title)))))] : null,
      skills.length ? [h("h3", {}, t("sdg_skills")), h("div", { class: "chips" }, capped(skills, (x) =>
        h("a", { class: "chip", href: `#/learn/${x.id}`, onclick: close }, skillShort(x.id))))] : null,
      h("p", { class: "sdg-more" }, h("a", { href: g.url, target: "_blank", rel: "noopener" }, `${t("sdg_un")} ↗`)))));
  document.body.append(dlg);
  dlg.showModal();
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
  close: "M6 6l12 12M18 6L6 18", user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4.5 21a7.5 7.5 0 0 1 15 0", send: "M12 19V5M5.5 11.5 12 5l6.5 6.5", copy: "M9 9h11v11H9zM5 15H4V4h11v1",
  eye: "M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12zM12 14.8a2.8 2.8 0 1 0 0-5.6 2.8 2.8 0 0 0 0 5.6z", layers: "M12 3l9 5-9 5-9-5 9-5zM3 12l9 5 9-5M3 16.5l9 5 9-5", arrowLeft: "M19 12H5m6-6-6 6 6 6",
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
  // achievements
  star: "M12 2.6l2.93 5.94 6.55.95-4.74 4.62 1.12 6.53L12 17.56l-5.86 3.08 1.12-6.53L2.52 9.49l6.55-.95z",
  moon: "M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z", calendar: "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
  trophy: "M7 4h10v5a5 5 0 0 1-10 0zM7 6H4a3 3 0 0 0 3.5 4M17 6h3a3 3 0 0 1-3.5 4M12 14v4M8 21h8M9.5 18h5",
  crown: "M3 8l4.5 4L12 5l4.5 7L21 8l-2 11H5zM5 19h14", volume: "M4 9h4l5-4v14l-5-4H4zM16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12",
  mute: "M4 9h4l5-4v14l-5-4H4zM17 9.5l5 5M22 9.5l-5 5", menu: "M4 6h16M4 12h16M4 18h16",
  // rewards
  gift: "M4 11h16v9H4zM3 7h18v4H3zM12 7v13M12 7C10.5 4 7 3.5 7 5.8 7 7 9.5 7 12 7zm0 0c1.5-3 5-3.5 5-1.2C17 7 14.5 7 12 7z",
  sticker: "M4 4h16v9l-7 7H4zM20 13h-5a2 2 0 0 0-2 2v5", notebook: "M6 3h12v18H6zM9 3v18M12.5 8h3M12.5 12h3",
  coffee: "M4 9h13v5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5zM17 10.5h1.5a2.5 2.5 0 0 1 0 5H17M8 3c-.8 1 .8 2 0 3M12 3c-.8 1 .8 2 0 3",
  cup: "M6 8h12M7 8l1.5 13h7L17 8M12 8l2.5-5H17M10 17h.01M12 18.5h.01M14 17h.01", mug: "M5 6h11v11a3 3 0 0 1-3 3H8a3 3 0 0 1-3-3zM16 9h2a2 2 0 0 1 0 4h-2",
  bag: "M5 8h14l-1 13H6zM9 8V6a3 3 0 0 1 6 0v2", shirt: "M8 3 3 6l2 4 3-1v12h8V9l3 1 2-4-5-3a4 4 0 0 1-8 0z",
  mouse: "M12 3a6 6 0 0 1 6 6v6a6 6 0 0 1-12 0V9a6 6 0 0 1 6-6zM12 7v4", battery: "M3 7h16v10H3zM21 10.5v3M7 10v4M11 10v4",
  wallet: "M3 7h16a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H3zM3 7l12-4v4M16.5 13.5h.01", stand: "M6 4h12v8H6zM4 15h16M8 15l-1.5 5M16 15l1.5 5",
  camera: "M12 3a6 6 0 1 1 0 12 6 6 0 0 1 0-12zM12 7.5a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zM8 21h8M12 15v6",
  backpack: "M7 9a5 5 0 0 1 10 0v12H7zM10 4V3h4v1M9 14h6v4H9z", speaker: "M7 3h10v18H7zM12 17.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM12 7h.01",
  earbuds: "M10 8a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM7 11v8M20 8a3 3 0 1 1-6 0 3 3 0 0 1 6 0zM17 11v8", ereader: "M6 3h12v18H6zM9 7h6M9 10h6M9 13h4",
  monitor: "M3 4h18v12H3zM9 20h6M12 16v4", watch: "M8 7h8v10H8zM9 7l1-4h4l1 4M9 17l1 4h4l1-4M12 10v2l1.5 1",
  tablet: "M5 3h14v18H5zM11 18h2", phone: "M7 2h10v20H7zM11 18h2", laptop: "M5 5h14v10H5zM3 19h18l-2-4H5z",
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

export async function ensurePathway(rid) {
  const key = JSON.stringify([state.asOf, state.scenario, rid, state.profile]);
  if (state.pathwayKey === key) return;
  state.pathway = await api("/api/pathway", { as_of: state.asOf, scenario: state.scenario, profile: state.profile, role_id: rid });
  state.pathwayKey = key;
}

export async function ensureCourses() {
  if (!state.courses) state.courses = (await api("/api/learn/courses")).courses;
}
