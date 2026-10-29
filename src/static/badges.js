// Achievements (on My profile): 100 medals for learning, coming back and exploring. 70 bronze for first steps, 25 silver
// for real progress and 5 gold for the legends. Most are worked out from the progress the site already keeps (lessons,
// tests, certificates, the streak, readiness for the goal); the rest count things done along the way (`state.tally`).
// A new medal slides in at the top of the page with a chime, and is kept like the rest of the progress: in this tab
// for a guest, in the account for someone signed in.
import { h } from "./charts.js";
import { state, store, t, loc, account, hasProfile, skillById, dayKey, shiftDay, streak, icon, go, dateLabel } from "./core.js";

// id, tier (1 bronze, 2 silver, 3 gold), group, icon, the number to reach, and how far the person is. Options: `d` a
// description shared by a ladder ("Complete {n} lessons."), `unit` "h" (minutes shown as hours) or "%", `href` where
// to earn it, `vars` more words for the description.
const B = (id, tier, group, ic, goal, get, more = {}) => ({ id, tier, group, icon: ic, goal, get, ...more });
const LEARN = { href: "#/learn" }, PATH = { href: "#/path" }, MATCHES = { href: "#/results" };

export const BADGES = [
  // getting started
  B("hello", 1, "start", "sparkles", 1, (c) => c.days),
  B("profile", 1, "start", "user", 1, (c) => c.profile, { href: "#/start?step=1" }),
  B("skills5", 1, "start", "layers", 5, (c) => c.skills, { d: "skills", href: "#/start?step=2" }),
  B("skills10", 1, "start", "layers", 10, (c) => c.skills, { d: "skills", href: "#/start?step=2" }),
  B("interests", 1, "start", "heart", 1, (c) => c.tiles, { href: "#/start?step=3" }),
  B("exp", 1, "start", "briefcase", 1, (c) => c.experience, { href: "#/me" }),
  B("cv", 1, "start", "upload", 1, (c) => (c.origin === "cv" ? 1 : 0), { href: "#/start?step=1" }),
  B("example", 1, "start", "users", 1, (c) => (c.origin === "persona" ? 1 : 0), { href: "#/" }),
  B("signin", 1, "start", "shield", 1, (c) => c.signedIn),
  B("me", 1, "start", "eye", 1, (c) => c.page("me"), { vars: () => ({ page: t("me_title") }) }),
  B("matches", 1, "start", "list", 1, (c) => c.page("results"), MATCHES),
  B("why", 1, "start", "bulb", 1, (c) => c.n("why"), { ...MATCHES, vars: () => ({ why: t("why") }) }),
  // my path
  B("plan1", 1, "path", "route", 1, (c) => c.count("plans"), MATCHES),
  B("plans3", 1, "path", "map", 3, (c) => c.count("plans"), { d: "plans", ...MATCHES }),
  B("plans10", 1, "path", "map", 10, (c) => c.count("plans"), { d: "plans", ...MATCHES }),
  B("goal", 1, "path", "target", 1, (c) => c.goals, MATCHES),
  B("goal2", 1, "path", "refresh", 2, (c) => c.goals, MATCHES),
  B("step1", 1, "path", "check", 1, (c) => c.n("steps"), PATH),
  B("mark", 1, "path", "check", 1, (c) => c.marked, PATH),
  B("ready50", 1, "path", "target", 50, (c) => c.ready, { d: "ready", unit: "%", ...PATH }),
  B("gain5", 1, "path", "trend", 5, (c) => c.gain, { d: "gain", ...PATH }),
  B("gain15", 2, "path", "trend", 15, (c) => c.gain, { d: "gain", ...PATH }),
  B("gain30", 2, "path", "rocket", 30, (c) => c.gain, { d: "gain", ...PATH }),
  B("ready75", 2, "path", "target", 75, (c) => c.ready, { d: "ready", unit: "%", ...PATH }),
  B("half_path", 2, "path", "route", 50, (c) => c.n("path"), { unit: "%", ...PATH }),
  B("dream", 3, "path", "trophy", 100, (c) => c.n("path"), { unit: "%", ...PATH }),
  // learning
  B("l1", 1, "learn", "bookOpen", 1, (c) => c.lessons, LEARN),
  B("l5", 1, "learn", "book", 5, (c) => c.lessons, { d: "lessons", ...LEARN }),
  B("l10", 1, "learn", "book", 10, (c) => c.lessons, { d: "lessons", ...LEARN }),
  B("l25", 1, "learn", "book", 25, (c) => c.lessons, { d: "lessons", ...LEARN }),
  B("l50", 2, "learn", "book", 50, (c) => c.lessons, { d: "lessons", ...LEARN }),
  B("l100", 2, "learn", "grad", 100, (c) => c.lessons, { d: "lessons", ...LEARN }),
  B("l250", 2, "learn", "grad", 250, (c) => c.lessons, { d: "lessons", ...LEARN }),
  B("l500", 3, "learn", "crown", 500, (c) => c.lessons, { d: "lessons", ...LEARN }),
  B("day3", 1, "learn", "bolt", 3, (c) => c.maxL, { d: "day", ...LEARN }),
  B("day5", 1, "learn", "bolt", 5, (c) => c.maxL, { d: "day", ...LEARN }),
  B("day10", 2, "learn", "bolt", 10, (c) => c.maxL, { d: "day", ...LEARN }),
  B("h1", 1, "learn", "clock", 60, (c) => c.minutes, { unit: "h", ...LEARN }),
  B("h5", 1, "learn", "clock", 300, (c) => c.minutes, { d: "hours", unit: "h", ...LEARN }),
  B("h10", 2, "learn", "clock", 600, (c) => c.minutes, { d: "hours", unit: "h", ...LEARN }),
  B("c3", 1, "learn", "layers", 3, (c) => c.started, { d: "courses", ...LEARN }),
  B("c5", 1, "learn", "layers", 5, (c) => c.started, { d: "courses", ...LEARN }),
  B("read1", 1, "learn", "bookOpen", 1, (c) => c.read, LEARN),
  B("read3", 2, "learn", "bookOpen", 3, (c) => c.read, LEARN),
  B("cat_ai_data", 1, "learn", "cpu", 1, (c) => c.cat("ai_data"), { d: "cat", vars: () => ({ cat: loc(state.meta.categories.ai_data) }), ...LEARN }),
  B("cat_digital", 1, "learn", "code", 1, (c) => c.cat("digital"), { d: "cat", vars: () => ({ cat: loc(state.meta.categories.digital) }), ...LEARN }),
  B("cat_green", 1, "learn", "leaf", 1, (c) => c.cat("green"), { d: "cat", vars: () => ({ cat: loc(state.meta.categories.green) }), ...LEARN }),
  B("cat_human", 1, "learn", "users", 1, (c) => c.cat("human"), { d: "cat", vars: () => ({ cat: loc(state.meta.categories.human) }), ...LEARN }),
  B("cat_all", 1, "learn", "globe", 4, (c) => c.cats.size, LEARN),
  // tests and certificates
  B("t1", 1, "tests", "check", 1, (c) => c.chapters, LEARN),
  B("t5", 1, "tests", "check", 5, (c) => c.chapters, { d: "tests", ...LEARN }),
  B("t10", 2, "tests", "check", 10, (c) => c.chapters, { d: "tests", ...LEARN }),
  B("t25", 2, "tests", "check", 25, (c) => c.chapters, { d: "tests", ...LEARN }),
  B("tday3", 1, "tests", "bolt", 3, (c) => c.maxT, LEARN),
  B("perfect1", 1, "tests", "sparkles", 1, (c) => c.perfect, LEARN),
  B("perfect5", 2, "tests", "sparkles", 5, (c) => c.perfect, LEARN),
  B("comeback", 1, "tests", "refresh", 1, (c) => c.comeback, LEARN),
  B("final1", 2, "tests", "award", 1, (c) => c.finals, LEARN),
  B("ace", 1, "tests", "award", 1, (c) => c.ace, LEARN),
  B("cert1", 1, "tests", "award", 1, (c) => c.certs, LEARN),
  B("cert3", 2, "tests", "award", 3, (c) => c.certs, { d: "certs", ...LEARN }),
  B("cert5", 2, "tests", "award", 5, (c) => c.certs, { d: "certs", ...LEARN }),
  B("cert10", 3, "tests", "trophy", 10, (c) => c.certs, { d: "certs", ...LEARN }),
  B("certcat", 2, "tests", "globe", 4, (c) => c.certCats, LEARN),
  // habits
  B("s2", 1, "habit", "star", 2, (c) => c.best, { d: "streak" }),
  B("s3", 1, "habit", "star", 3, (c) => c.best, { d: "streak" }),
  B("s5", 1, "habit", "star", 5, (c) => c.best, { d: "streak" }),
  B("s7", 2, "habit", "star", 7, (c) => c.best, { d: "streak" }),
  B("s14", 2, "habit", "star", 14, (c) => c.best, { d: "streak" }),
  B("s30", 2, "habit", "star", 30, (c) => c.best, { d: "streak" }),
  B("s100", 3, "habit", "star", 100, (c) => c.best, { d: "streak" }),
  B("d7", 1, "habit", "calendar", 7, (c) => c.days, { d: "days" }),
  B("d30", 2, "habit", "calendar", 30, (c) => c.days, { d: "days" }),
  B("phoenix", 1, "habit", "refresh", 1, (c) => c.phoenix),
  B("active3", 1, "habit", "calendar", 3, (c) => c.learnDays, { d: "learn_days", ...LEARN }),
  B("active10", 2, "habit", "calendar", 10, (c) => c.learnDays, { d: "learn_days", ...LEARN }),
  B("week_half", 1, "habit", "clock", 50, (c) => c.week, { unit: "%", ...LEARN }),
  B("week_goal", 2, "habit", "clock", 100, (c) => c.week, { unit: "%", ...LEARN }),
  B("night", 1, "habit", "moon", 1, (c) => c.has("times", "night"), LEARN),
  B("early", 1, "habit", "sun", 1, (c) => c.has("times", "early"), LEARN),
  B("lunch", 1, "habit", "clock", 1, (c) => c.has("times", "lunch"), LEARN),
  B("weekend", 1, "habit", "calendar", 1, (c) => c.weekend, LEARN),
  // exploring
  B("trends", 1, "explore", "trend", 1, (c) => c.page("trends"), { href: "#/trends", vars: () => ({ page: t("nav_trends") }) }),
  B("pace", 1, "explore", "bolt", 3, (c) => c.count("paces"), { ...MATCHES, vars: () => ({ a: t("pace_slow"), b: t("pace_moderate"), c: t("pace_fast") }) }),
  B("chat1", 1, "explore", "chat", 1, (c) => c.chat, { href: "#/chat" }),
  B("chat10", 1, "explore", "chat", 10, (c) => c.chat, { href: "#/chat" }),
  B("work", 1, "explore", "briefcase", 1, (c) => c.has("modes", "work"), { href: "#/next", vars: () => ({ page: t("nav_next") }) }),
  B("study", 1, "explore", "grad", 1, (c) => c.has("modes", "study"), { href: "#/next", vars: () => ({ page: t("nav_next") }) }),
  B("countries3", 1, "explore", "globe", 3, (c) => c.countries, { href: "#/next" }),
  B("remote", 1, "explore", "wifi", 1, (c) => c.has("countries", "REMOTE"), { href: "#/next" }),
  B("polyglot", 1, "explore", "message", 3, (c) => c.count("langs")),
  B("sdg1", 1, "explore", "leaf", 1, (c) => c.count("sdgs"), { href: "#/" }),
  B("sdg5", 1, "explore", "globe", 5, (c) => c.count("sdgs"), { href: "#/" }),
  B("how", 1, "explore", "cpu", 1, (c) => c.page("how"), { href: "#/how", vars: () => ({ page: t("nav_how") }) }),
  B("teams", 1, "explore", "users", 1, (c) => c.page("teams"), { href: "#/teams", vars: () => ({ page: t("nav_teams") }) }),
  B("catalog", 1, "explore", "book", 1, (c) => c.page("learn"), LEARN),
  // the collection itself
  B("a10", 1, "meta", "trophy", 10, (c) => c.earned, { d: "ach" }),
  B("a25", 2, "meta", "trophy", 25, (c) => c.earned, { d: "ach" }),
  B("a50", 2, "meta", "trophy", 50, (c) => c.earned, { d: "ach" }),
  B("all", 3, "meta", "crown", 99, (c) => c.earned),
];
const BY = Object.fromEntries(BADGES.map((b) => [b.id, b]));
const TIERS = [3, 2, 1];

export const badgeTitle = (b) => t(`bt_${b.id}`);
export const badgeText = (b) => t(b.d ? `bd_${b.d}` : `bd_${b.id}`, { n: b.unit === "h" ? b.goal / 60 : b.goal, ...(b.vars ? b.vars() : {}) });

// ---------------------------------------------------------------- how far the person is
function context() {
  const skills = skillById(), tally = state.tally || {};
  const courses = state.courses ? Object.fromEntries(state.courses.map((x) => [x.skill, x])) : null;
  const failed = new Set(tally.failed || []);
  const c = { lessons: 0, chapters: 0, finals: 0, perfect: 0, comeback: 0, ace: 0, started: 0, read: courses ? 0 : null, areas: new Set() };
  let estimate = 0;
  for (const [sid, x] of Object.entries(state.learned || {})) {
    const n = (x?.done || []).length;
    c.lessons += n;
    if (n) { c.started++; if (skills[sid]) c.areas.add(skills[sid].category); }
    const passes = Object.entries(x?.chapters || {}).map(([k, r]) => [`${sid}/${k}`, r]);
    c.chapters += passes.length;
    if (x?.final) {
      c.finals++;
      passes.push([`${sid}/final`, x.final]);
      if (!failed.has(`${sid}/final`)) c.ace++;
    }
    for (const [key, r] of passes) {
      if (r?.total && r.score === r.total) c.perfect++;
      if (failed.has(key)) c.comeback++;
    }
    const course = courses?.[sid];
    if (course?.lessons) {
      estimate += Math.min(n, course.lessons) * (course.minutes / course.lessons);
      if (n >= course.lessons) c.read++;
    }
  }
  c.cats = c.areas;
  c.cat = (id) => (c.areas.has(id) ? 1 : 0);
  const certs = Object.keys(state.certs || {});
  c.certs = certs.length;
  c.certCats = new Set(certs.map((sid) => skills[sid]?.category).filter(Boolean)).size;

  // by day: visits, lessons, tests and minutes
  const activity = state.activity || {};
  let logged = 0;
  Object.assign(c, { days: 0, learnDays: 0, maxL: 0, maxT: 0, weekend: 0 });
  for (const [d, a] of Object.entries(activity)) {
    if (a?.v) c.days++;
    if (a?.l) {
      c.learnDays++;
      if (new Date(`${d}T12:00:00`).getDay() === 6 && activity[shiftDay(d, 1)]?.l) c.weekend = 1;
    }
    c.maxL = Math.max(c.maxL, a?.l || 0);
    c.maxT = Math.max(c.maxT, a?.t || 0);
    logged += a?.m || 0;
  }
  c.minutes = Math.round(Math.max(logged, estimate));
  const today = dayKey();
  let week = 0;
  for (let i = 0; i <= (new Date().getDay() + 6) % 7; i++) week += activity[shiftDay(today, -i)]?.m || 0;
  c.week = Math.floor((week / ((state.profile.hours_per_week || 6) * 60)) * 100);
  const st = streak();
  c.best = st.best;
  c.phoenix = st.ended >= 2 ? 1 : 0;

  // the goal: readiness now, and how much it grew since the goal was set
  c.ready = 0;
  c.gain = 0;
  for (const e of Object.values(state.path || {})) {
    const fits = Object.entries(e?.fits || {}).sort(([a], [b]) => (a < b ? -1 : 1)).map(([, v]) => v);
    if (!fits.length) continue;
    c.ready = Math.max(c.ready, fits[fits.length - 1]);
    c.gain = Math.max(c.gain, Math.max(...fits) - fits[0]);
  }
  c.goals = Math.max(Object.keys(state.path || {}).length, state.goal ? 1 : 0);
  c.marked = Object.values(state.progress || {}).some((p) => Object.values(p || {}).some(Boolean)) ? 1 : 0;

  // the profile
  const p = state.profile;
  c.profile = hasProfile() ? 1 : 0;
  c.skills = Object.keys(p.skills || {}).length;
  c.tiles = (state.tiles || []).length ? 1 : 0;
  c.experience = p.years_experience != null ? 1 : 0;
  c.origin = state.origin?.type || null;
  c.signedIn = account.user ? 1 : 0;

  // things done along the way
  const list = (k) => (Array.isArray(tally[k]) ? tally[k] : []);
  c.page = (name) => (list("pages").includes(name) ? 1 : 0);
  c.has = (k, v) => (list(k).includes(v) ? 1 : 0);
  c.count = (k) => list(k).length;
  c.n = (k) => (typeof tally[k] === "number" ? tally[k] : 0);
  c.countries = list("countries").filter((x) => x !== "REMOTE").length;
  c.chat = Math.max(c.n("chat"), (state.coach?.messages || store.get("coach", [])).filter((m) => m.role === "user").length);
  c.earned = Object.keys(state.badges || {}).filter((id) => BY[id]).length;
  return c;
}

const value = (b, c) => { const v = b.get(c); return typeof v === "number" && Number.isFinite(v) ? v : null; };
const reached = (b, c) => { const v = value(b, c); return v !== null && v >= b.goal; };

// After anything changes (every page drawn, a new day's visit): what is newly earned is saved and announced.
export function checkBadges() {
  if (!state.meta) return [];
  const c = context(), got = { ...state.badges }, at = new Date().toISOString(), fresh = [];
  const earn = (b) => { got[b.id] = at; fresh.push(b); };
  for (const b of BADGES) if (!got[b.id] && b.group !== "meta" && reached(b, c)) earn(b);
  for (let more = true; more;) {                    // the collection medals count the others, the ones just earned too
    more = false;
    c.earned = Object.keys(got).filter((id) => BY[id]).length;
    for (const b of BADGES) if (!got[b.id] && b.group === "meta" && reached(b, c)) { earn(b); more = true; }
  }
  if (!fresh.length) return fresh;
  state.badges = got;
  store.set("badges", got);
  announce(fresh);
  return fresh;
}

// The closest medals still to earn: the furthest along first, then the easier ones.
function upNext(c, got, n) {
  return BADGES.map((b, i) => ({ b, i, v: got[b.id] || b.group === "meta" ? null : value(b, c) }))
    .filter((x) => x.v !== null)
    .map((x) => ({ ...x, r: Math.min(1, x.v / x.b.goal) }))
    .sort((x, y) => y.r - x.r || x.b.tier - y.b.tier || x.i - y.i)
    .slice(0, n);
}

function progressLabel(b, v) {
  const d = Math.min(v, b.goal);
  if (b.unit === "h") return t("ach_prog_h", { d: Math.floor(d / 6) / 10, n: b.goal / 60 });
  if (b.unit === "%") return `${Math.round(d)}% / ${b.goal}%`;
  return t("ach_prog", { d, n: b.goal });
}

export function medal(b, got, size = "") {
  return h("span", { class: `medal t${b.tier}${got ? "" : " locked"}${size ? ` ${size}` : ""}`, "aria-hidden": "true" }, icon(b.icon));
}

export function openBadge(id) {
  if (id) state.badgeSel = id;
  state.scrollTo = "achievements";
  go("#/me");
}

// ---------------------------------------------------------------- the chime
// A bell-like note per medal: a two-note ding for bronze, a rising run for silver, a small fanfare for gold. Browsers
// let a page play sound only after the person has clicked, tapped or typed on it, so a chime due before that plays on
// the first tap, while its notification is still on screen.
const TUNES = {
  1: [[880, 0, 0.32], [1318.5, 0.1, 0.55]],
  2: [[784, 0, 0.28], [1046.5, 0.08, 0.28], [1318.5, 0.16, 0.3], [1568, 0.24, 0.8]],
  3: [[523.25, 0, 0.22], [659.25, 0.09, 0.22], [784, 0.18, 0.22], [1046.5, 0.3, 1.1], [1318.5, 0.3, 1.1], [1568, 0.3, 1.1],
    [2093, 0.52, 0.45], [2637, 0.62, 0.45], [3136, 0.72, 0.6]],
};
let audio = null, due = null;
export const soundOn = () => store.get("sound", true) !== false;

function play(tier) {
  const a = audio, out = a.createGain();
  out.gain.value = 0.5;
  out.connect(a.destination);
  const t0 = a.currentTime + 0.02;
  for (const [freq, at, dur] of TUNES[tier] || TUNES[1]) {
    for (const [mult, type, vol] of [[1, "sine", 0.22], [2, "triangle", 0.04]]) {     // the note and a soft octave above
      const o = a.createOscillator(), g = a.createGain();
      o.type = type;
      o.frequency.value = freq * mult;
      g.gain.setValueAtTime(0.0001, t0 + at);
      g.gain.exponentialRampToValueAtTime(vol, t0 + at + 0.012);
      g.gain.exponentialRampToValueAtTime(0.0001, t0 + at + dur);
      o.connect(g);
      g.connect(out);
      o.start(t0 + at);
      o.stop(t0 + at + dur + 0.05);
    }
  }
}

export function chime(tier) {
  if (!soundOn()) return;
  if (audio?.state === "running") play(tier);
  else due = { tier, until: Date.now() + 5000 };
}

function wake() {
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC || audio?.state === "running") return;
  try { audio ||= new AC(); } catch { return; }
  audio.resume().then(() => {
    if (due && Date.now() < due.until && audio.state === "running") play(due.tier);
    due = null;
  }).catch(() => {});
}
for (const ev of ["pointerdown", "keydown", "touchend"]) addEventListener(ev, wake, { capture: true, passive: true });

// ---------------------------------------------------------------- the notification at the top of the page
let box = null;
function announce(list) {
  const top = [...list].sort((a, b) => b.tier - a.tier);
  const shown = top.length > 3 ? top.slice(0, 2) : top;      // many at once (a first visit after a lot of progress): a summary
  if (!box?.isConnected) {
    box = h("div", { class: "pushes", "aria-live": "polite" });
    document.body.append(box);
  }
  shown.forEach((b, i) => setTimeout(() => push(b), i * 280));
  if (top.length > shown.length) setTimeout(() => push(null, top.length - shown.length), shown.length * 280);
  chime(top[0].tier);
}

function push(b, more = 0) {
  const tier = b ? b.tier : 1;
  let gone = false;
  const close = () => {
    if (gone) return;
    gone = true;
    el.classList.add("out");
    setTimeout(() => el.remove(), 320);
  };
  const el = h("div", { class: `push t${tier}` },
    tier > 1 ? h("span", { class: "push-glow" }) : null,                  // silver and gold shine; gold also throws stars
    h("button", { type: "button", class: "push-main", onclick: () => { close(); openBadge(b?.id); } },
      b ? medal(b, true, "sm") : h("span", { class: "medal t1 sm more", "aria-hidden": "true" }, `+${more}`),
      h("span", { class: "push-text" },
        h("span", { class: "push-kicker" }, b ? `${t("ach_unlocked")} · ${t(`ach_tier_${tier}`)}` : t("ach_unlocked_many")),
        h("b", {}, b ? badgeTitle(b) : t("ach_and_more", { n: more })),
        h("span", { class: "push-desc" }, b ? badgeText(b) : t("ach_tap_all")))),
    h("button", { type: "button", class: "push-x", "aria-label": t("close"), onclick: close }, icon("close")),
    tier === 3 ? Array.from({ length: 10 }, (_, i) => h("span", { class: "spark", style: { "--a": `${i * 36}deg` } })) : null);
  box.append(el);
  setTimeout(close, [0, 4500, 5500, 7500][tier]);
}

// ---------------------------------------------------------------- the section on My profile
function latest(got) {
  const [id] = Object.entries(got).filter(([k]) => BY[k]).sort(([, a], [, b]) => (a < b ? 1 : -1))[0] || [];
  return BY[id] || null;
}

function soundButton() {
  const on = soundOn();
  return h("button", { type: "button", class: "btn btn-secondary btn-sm ach-sound", "aria-pressed": String(on),
    onclick: (e) => { store.set("sound", !on); if (!on) chime(1); e.currentTarget.replaceWith(soundButton()); } },
  icon(on ? "volume" : "mute"), t(on ? "ach_sound_on" : "ach_sound_off"));
}

function detail(b, c, got) {
  const when = got[b.id], v = value(b, c);
  const pct = v === null ? 0 : Math.min(100, Math.round((v / b.goal) * 100));
  return h("div", { class: `ach-detail${when ? " got" : ""}` },
    medal(b, !!when, "lg"),
    h("div", { class: "ach-detail-text" },
      h("p", { class: `ach-kicker t${b.tier}` }, `${t(`ach_tier_${b.tier}`)} · ${t(`ach_group_${b.group}`)}`),
      h("h3", {}, badgeTitle(b)),
      h("p", {}, badgeText(b)),
      when ? h("p", { class: "ach-when" }, icon("check"), t("ach_got", { date: dateLabel(when) }))
        : h("div", { class: "ach-prog" },
          b.goal > 1 && v !== null ? [h("div", { class: "progress" }, h("span", { style: { width: `${pct}%` } })), h("span", { class: "small muted" }, progressLabel(b, v))]
            : h("span", { class: "small muted" }, t("ach_locked")),
          b.href ? h("a", { class: "btn btn-secondary btn-sm", href: b.href }, t("ach_go"), " →") : null)));
}

function nextRow(b, c, onclick) {
  const v = value(b, c) ?? 0, pct = Math.min(100, Math.round((v / b.goal) * 100));
  return h("button", { type: "button", class: "ach-row", onclick },
    medal(b, false, "sm"),
    h("span", { class: "ach-row-text" }, h("b", {}, badgeTitle(b)), h("span", { class: "small muted" }, badgeText(b)),
      b.goal > 1 ? h("span", { class: "ach-row-bar" }, h("span", { class: "pbar" }, h("span", { style: { width: `${pct}%` } })),
        h("span", { class: "tiny muted" }, progressLabel(b, v))) : null));
}

const tierCount = (tier, got) => { const all = BADGES.filter((b) => b.tier === tier); return [all.filter((b) => got[b.id]).length, all.length]; };

export function achievementsSection() {
  const c = context(), got = state.badges || {};
  const earned = BADGES.filter((b) => got[b.id]).length;
  const next = upNext(c, got, 3);
  const sel = BY[state.badgeSel] || latest(got) || next[0]?.b || BADGES[0];
  const pick = (b) => {                  // the medal's details, without redrawing the page
    state.badgeSel = b.id;
    const fresh = achievementsSection();
    document.getElementById("achievements")?.replaceWith(fresh);
    fresh.querySelector(`[data-badge="${b.id}"]`)?.focus({ preventScroll: true });
  };
  return h("section", { class: "card me-card ach", id: "achievements" },
    h("div", { class: "ach-head" },
      h("div", {}, h("h2", {}, t("ach_title")), h("p", { class: "small muted" }, t("ach_sub"))),
      soundButton()),
    h("div", { class: "ach-sum" },
      h("b", {}, t("ach_of", { n: earned, total: BADGES.length })),
      h("div", { class: "progress" }, h("span", { style: { width: `${Math.round((earned / BADGES.length) * 100)}%` } })),
      h("div", { class: "ach-tiers" }, TIERS.map((tier) => {
        const [n, all] = tierCount(tier, got);
        return h("span", {}, h("i", { class: `dot t${tier}` }), `${t(`ach_tier_${tier}`)} ${n}/${all}`);
      }))),
    h("div", { class: "ach-top" },
      detail(sel, c, got),
      next.length ? h("div", { class: "ach-next" }, h("p", { class: "k" }, t("ach_next")), next.map(({ b }) => nextRow(b, c, () => pick(b))))
        : h("p", { class: "ach-next muted" }, t("ach_done_all"))),
    TIERS.map((tier) => h("div", { class: "ach-tier" },
      h("h3", {}, h("i", { class: `dot t${tier}` }), t(`ach_tier_${tier}`), h("span", { class: "muted" }, ` ${tierCount(tier, got).join("/")}`)),
      h("div", { class: "ach-wall" }, BADGES.filter((b) => b.tier === tier).map((b) =>
        h("button", { type: "button", class: "ach-cell", "data-badge": b.id, "aria-pressed": String(b.id === sel.id), title: badgeTitle(b),
          "aria-label": `${badgeTitle(b)}: ${got[b.id] ? t("ach_got", { date: dateLabel(got[b.id]) }) : t("ach_locked")}`, onclick: () => pick(b) },
        medal(b, !!got[b.id])))))),
    account.user ? null : h("p", { class: "small muted ach-guest" }, t("ach_guest")));
}

// ---------------------------------------------------------------- the card on My path
export function badgesCard() {
  const c = context(), got = state.badges || {};
  const earned = BADGES.filter((b) => got[b.id]).length;
  return h("section", { class: "card ach-mini" }, h("h3", {}, t("ach_title")),
    h("p", { class: "small muted" }, t("ach_of", { n: earned, total: BADGES.length })),
    h("div", { class: "progress" }, h("span", { style: { width: `${Math.round((earned / BADGES.length) * 100)}%` } })),
    h("div", { class: "ach-next" }, upNext(c, got, 3).map(({ b }) => nextRow(b, c, () => openBadge(b.id)))),
    h("a", { class: "me-link", href: "#/me", onclick: (e) => { e.preventDefault(); openBadge(); } }, t("ach_all"), " →"));
}
