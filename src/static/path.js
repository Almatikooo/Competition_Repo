// My path (#/path): the job the person works towards and everything done on the way. Readiness for that job grows
// as skills grow (a passed final test makes a skill Advanced). The roadmap follows real course progress, the next
// lesson is one tap away, and an activity calendar, the week's goal and milestones keep the habit going. The star
// in the header is the visit streak, shown to signed-in people.
import { h, s } from "./charts.js";
import { state, store, t, api, $, account, hasProfile, roleById, roleTitle, skillName, icon, go, rerender, dateLabel,
  ensureMatches, ensureCourses, ensurePathway, dayKey, shiftDay, streak } from "./core.js";
import { nextStep, testHref, hoursLabel } from "./learn.js";

const STAR = "M12 2.6l2.93 5.94 6.55.95-4.74 4.62 1.12 6.53L12 17.56l-5.86 3.08 1.12-6.53L2.52 9.49l6.55-.95z";
export const star = (cls = "star") => s("svg", { viewBox: "0 0 24 24", class: cls, "aria-hidden": "true" }, s("path", { d: STAR }));
const LOCALES = { en: "en-MY", ms: "ms-MY", zh: "zh-CN" };
const PHASES = ["foundation", "core", "supporting"];
const level = (n) => (n ? t(`me_lvl_${n}`) : t("path_lvl_0"));
const noon = (day) => `${day}T12:00:00`;                       // a calendar day as local noon, for date labels
const coursesBy = () => Object.fromEntries((state.courses || []).map((c) => [c.skill, c]));
const currentGoal = () => (state.goal && roleById()[state.goal] ? state.goal : null);

export function setGoal(rid) {
  state.goal = rid;
  store.set("goal", rid);
  store.set("focusRole", rid);                                 // Opportunities searches this job first
  go("#/path");
}

// ---------------------------------------------------------------- data
export async function ensurePath() {
  await ensureCourses();
  if (!hasProfile()) return;
  await ensureMatches();
  const goal = currentGoal();
  if (!goal) return;
  await ensurePathway(goal);
  track(goal);
  const next = roadmap(goal).find((x) => !x.done);
  if (next?.course && state.pathCourse?.skill !== next.skill) state.pathCourse = await api(`/api/learn/course/${encodeURIComponent(next.skill)}`);
}

// The steps as they were when the goal was set, so a skill that gets learned stays on the map as done (the plan
// itself only lists what is still missing). Readiness is kept by day, to show how it grew.
const snap = (st) => ({ skill: st.skill, hours: st.hours, to: st.to_level, phase: st.phase });
function track(goal) {
  const p = state.pathway, today = dayKey(), old = state.path[goal];
  const entry = old ? { ...old, steps: [...old.steps], fits: { ...old.fits } } : { since: today, steps: [], fits: {} };
  for (const st of p.steps) if (!entry.steps.some((x) => x.skill === st.skill)) entry.steps.push(snap(st));
  const days = Object.keys(entry.fits).sort();
  if (entry.fits[days[days.length - 1]] !== p.fit_now) entry.fits[today] = p.fit_now;
  entry.fits = Object.fromEntries(Object.entries(entry.fits).sort(([a], [b]) => (a < b ? -1 : 1)).slice(-120));
  if (JSON.stringify(entry) !== JSON.stringify(old)) {
    state.path = { ...state.path, [goal]: entry };
    store.set("path", state.path);
  }
}

// Each step with its real progress, in the plan's order. A step is done once its certificate is earned, its final
// test passed, it is marked done, or the skill is no longer missing from the profile.
function roadmap(goal) {
  const p = state.pathway, by = coursesBy();
  return (state.path[goal]?.steps || p.steps.map(snap)).map((x) => {
    const cur = p.steps.find((st) => st.skill === x.skill) || null;
    const course = by[x.skill] || null;
    const learned = state.learned[x.skill] || { done: [] };
    const lessons = course ? Math.min(learned.done.length, course.lessons) : 0;
    const tests = Object.keys(learned.chapters || {}).length;
    const cert = state.certs[x.skill] || null;
    const done = !cur || !!cert || !!learned.final || !!state.progress[goal]?.[x.skill];
    return { ...x, cur, course, lessons, tests, cert, done, level: state.profile.skills[x.skill] || 0,
      phase: PHASES.includes(x.phase) ? x.phase : "core", pct: done ? 100 : course ? Math.round((lessons / course.lessons) * 100) : 0 };
  });
}

const share = (steps) => {
  const total = steps.reduce((a, x) => a + x.hours, 0);
  return total ? Math.round(steps.reduce((a, x) => a + x.hours * x.pct, 0) / total) : 100;
};

function markStep(goal, sid) {
  state.progress = { ...state.progress, [goal]: { ...(state.progress[goal] || {}), [sid]: true } };
  store.set("progress", state.progress);
  rerender();
}

// ---------------------------------------------------------------- page
export function viewPath() {
  if (!hasProfile()) {
    return h("div", { class: "container" }, h("section", { class: "wizard", style: { textAlign: "center" } },
      h("h1", {}, t("start_title")), h("p", { class: "sub" }, t("start_sub")),
      h("div", { class: "wizard-actions", style: { justifyContent: "center" } }, h("a", { class: "btn btn-primary btn-lg", href: "#/start?step=1" }, t("hero_start")))));
  }
  const goal = currentGoal();
  return goal ? dashboard(goal) : h("div");
}

function dashboard(goal) {
  const p = state.pathway, entry = state.path[goal] || { since: dayKey(), fits: {} };
  const steps = roadmap(goal), done = steps.filter((x) => x.done).length, pct = share(steps);
  const fits = Object.entries(entry.fits).sort(([a], [b]) => (a < b ? -1 : 1));
  const gain = p.fit_now - (fits.length ? fits[0][1] : p.fit_now);
  const since = dateLabel(noon(entry.since));
  return h("div", {},
    h("section", { class: "page-head" }, h("div", { class: "container path-hero" },
      h("div", { class: "path-hero-text" },
        h("p", { class: "kicker" }, star(), t("path_kicker")),
        h("h1", {}, roleTitle(goal)),
        h("p", {}, gain ? t("path_since", { d: `${gain > 0 ? "+" : "−"}${Math.abs(gain)}%`, date: since }) : t("path_since_flat", { date: since }),
          " · ", p.steps.length ? t("path_eta", { weeks: p.weeks, h: p.hours_per_week }) : t("path_ready")),
        h("div", { class: "path-progress" },
          h("div", { class: "progress", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": 100, "aria-valuenow": pct }, h("span", { style: { width: `${pct}%` } })),
          h("p", { class: "small muted" }, t("path_progress", { p: pct, done, n: steps.length }))),
        h("div", { class: "row", style: { gap: "8px", marginTop: "16px", flexWrap: "wrap" } },
          h("a", { class: "btn btn-secondary btn-sm", href: `#/plan/${goal}` }, t("path_open_plan")),
          h("a", { class: "btn btn-link btn-sm", href: "#/results" }, t("path_all_roles")))),
      readiness(p.fit_now, fits.map(([, v]) => v)))),
    h("section", { class: "band", style: { paddingTop: "28px" } }, h("div", { class: "container grid-main" },
      h("div", { class: "stack" }, nextCard(goal, steps), roadmapCard(goal, steps)),
      h("div", { class: "stack" }, statsCard(steps), weekCard(), activityCard(), milestonesCard(steps, pct)))));
}

// Readiness for the goal, with how it moved since the goal was set.
function readiness(fit, history) {
  let trend = null;
  if (history.length > 1) {
    const w = 120, ht = 30, lo = Math.min(...history), span = Math.max(...history) - lo || 1;
    const pts = history.map((v, i) => `${((i / (history.length - 1)) * w).toFixed(1)},${(ht - 3 - ((v - lo) / span) * (ht - 6)).toFixed(1)}`).join(" ");
    trend = h("div", { class: "ready-trend" }, s("svg", { viewBox: `0 0 ${w} ${ht}`, "aria-hidden": "true" }, s("polyline", { points: pts })),
      h("span", { class: "small muted" }, `${history[0]}% → ${fit}%`));
  }
  return h("div", { class: "ready" },
    h("span", { class: "ring lg", style: { "--p": fit } }, h("span", {}, h("b", {}, `${fit}%`), h("small", {}, t("path_readiness")))), trend);
}

function nextCard(goal, steps) {
  const k = steps.findIndex((x) => !x.done);
  if (k < 0) {
    return h("section", { class: "card next-card complete" }, h("p", { class: "kicker" }, t("path_next")),
      h("h2", {}, t("path_complete_t")), h("p", { class: "muted" }, t("path_complete_d")),
      h("div", { class: "row", style: { gap: "8px", marginTop: "14px", flexWrap: "wrap" } },
        h("a", { class: "btn btn-primary", href: `#/next?mode=work&role=${goal}` }, icon("briefcase"), t("path_jobs")),
        h("a", { class: "btn btn-secondary", href: "#/results" }, t("path_new_goal"))));
  }
  const st = steps[k];
  const head = [h("p", { class: "kicker" }, `${t("path_next")} · ${t("path_step_of", { k: k + 1, n: steps.length })}`), h("h2", {}, skillName(st.skill))];
  if (st.course) {
    const c = state.pathCourse?.skill === st.skill ? state.pathCourse : null;
    const n = c ? nextStep(c) : null;
    const [href, line] = !n ? [`#/learn/${st.skill}`, t("path_next_start")]
      : n.kind === "lesson" ? [`#/learn/${st.skill}/${n.lesson.id}`, t("path_next_lesson", { n: n.n, title: n.lesson.title })]
        : n.kind === "test" ? [testHref(st.skill, n.n), t("path_next_test", { n: n.n })] : [testHref(st.skill, "final"), t("path_next_final")];
    return h("section", { class: "card next-card" }, head,
      h("p", { class: "next-line" }, h("span", { class: "muted" }, st.course.title), h("br"), h("b", {}, line)),
      st.lessons ? h("div", { class: "pbar" }, h("span", { style: { width: `${st.pct}%` } })) : null,
      h("a", { class: "btn btn-primary btn-lg", href }, st.lessons || st.tests ? t("path_btn_continue") : t("path_btn_start"), " →"));
  }
  const res = st.cur?.resource;
  return h("section", { class: "card next-card" }, head,
    res ? h("p", { class: "next-line" }, h("b", {}, res.title), h("br"), h("span", { class: "muted" }, `${res.provider} · ~${res.hours} h`)) : null,
    h("div", { class: "row", style: { gap: "8px", flexWrap: "wrap" } },
      res ? h("a", { class: "btn btn-primary", href: res.url, target: "_blank", rel: "noopener" }, t("path_open_res"), " ↗") : null,
      h("button", { type: "button", class: "btn btn-secondary", onclick: () => markStep(goal, st.skill) }, icon("check"), t("path_mark"))));
}

function roadmapCard(goal, steps) {
  const next = steps.find((x) => !x.done);
  return h("section", { class: "card" }, h("h3", {}, t("path_roadmap")),
    h("ol", { class: "roadmap" }, steps.map((x, i) => stepRow(goal, x, i + 1, x === next))));
}

function stepRow(goal, x, n, isNext) {
  const status = x.done ? "done" : x.lessons || x.tests ? "doing" : "todo";
  const res = x.cur?.resource;
  const detail = x.done ? (x.cert ? t("path_step_cert") : !x.cur ? t("path_step_have", { level: level(x.level) }) : t("path_step_marked"))
    : x.course ? [t("path_step_lessons", { d: x.lessons, n: x.course.lessons }), x.course.chapters ? t("path_step_tests", { d: x.tests, n: x.course.chapters }) : null].filter(Boolean).join(" · ")
      : res ? `${res.provider} · ~${res.hours} h` : "";
  const action = x.done ? (x.cert ? h("a", { class: "btn btn-link btn-sm", href: `#/certificate/${x.cert.token}` }, icon("award"), t("view_cert")) : null)
    : x.course ? h("a", { class: `btn btn-sm ${isNext ? "btn-primary" : "btn-secondary"}`, href: `#/learn/${x.skill}` }, x.lessons || x.tests ? t("path_btn_continue") : t("path_btn_start"))
      : [res ? h("a", { class: "btn btn-secondary btn-sm", href: res.url, target: "_blank", rel: "noopener" }, t("path_open_res"), " ↗") : null,
        h("button", { type: "button", class: "btn btn-link btn-sm", onclick: () => markStep(goal, x.skill) }, t("path_mark"))];
  return h("li", { class: `rm-step ${status}${isNext ? " next" : ""}` },
    h("span", { class: "rm-dot" }, x.done ? icon("check") : String(n)),
    h("div", { class: "rm-body" },
      h("div", { class: "rm-top" }, h("b", {}, skillName(x.skill)), h("span", { class: "rm-phase" }, t(`phase_${x.phase}`)),
        h("span", { class: "rm-level" }, x.done ? level(x.level) : `${level(x.cur?.from_level ?? x.level)} → ${level(x.to)}`)),
      status === "doing" && x.course ? h("div", { class: "pbar" }, h("span", { style: { width: `${x.pct}%` } })) : null,
      h("div", { class: "small muted" }, [detail, x.done ? null : `~${x.hours} h`].filter(Boolean).join(" · "))),
    h("div", { class: "rm-action" }, action));
}

function statsCard(steps) {
  const by = coursesBy();
  let lessons = 0, tests = 0, minutes = 0;
  for (const [sid, x] of Object.entries(state.learned || {})) {
    const n = (x.done || []).length, c = by[sid];
    lessons += n;
    tests += Object.keys(x.chapters || {}).length + (x.final ? 1 : 0);
    if (c?.lessons) minutes += n * (c.minutes / c.lessons);
  }
  const tile = (v, k) => h("div", { class: "stat" }, h("div", { class: "v" }, v), h("div", { class: "k" }, t(k)));
  return h("section", { class: "card" }, h("h3", {}, t("path_stats")),
    h("div", { class: "stats path-stats" }, tile(`${steps.filter((x) => x.done).length}/${steps.length}`, "st_steps"),
      tile(String(lessons), "st_lessons"), tile(String(tests), "st_tests"), tile(hoursLabel(Math.round(minutes)), "st_time")));
}

function weekCard() {
  const today = dayKey(), monday = (new Date().getDay() + 6) % 7;
  let minutes = 0;
  for (let i = 0; i <= monday; i++) minutes += state.activity[shiftDay(today, -i)]?.m || 0;
  const goalH = state.profile.hours_per_week || 6, doneH = Math.round(minutes / 6) / 10;
  const pct = Math.min(100, Math.round((minutes / (goalH * 60)) * 100));
  return h("section", { class: "card" }, h("h3", {}, t("path_week")),
    h("p", { class: "week-v" }, h("b", {}, t("path_week_v", { done: doneH, goal: goalH }))),
    h("div", { class: "progress" }, h("span", { style: { width: `${pct}%` } })),
    h("p", { class: "small muted", style: { marginTop: "6px" } }, pct >= 100 ? t("path_week_met") : t("path_week_left", { left: Math.round((goalH - doneH) * 10) / 10 })));
}

const describe = (a) => [a.l ? t("act_lessons", { n: a.l }) : null, a.t ? t("act_tests", { n: a.t }) : null].filter(Boolean).join(", ")
  || (a.v ? t("act_visit") : t("act_none"));

// Twelve weeks, a column per week from Monday: the darker the day, the more was done.
function activityCard() {
  const today = dayKey(), first = shiftDay(today, -(77 + ((new Date().getDay() + 6) % 7)));
  let active = 0;
  const cells = Array.from({ length: 84 }, (_, i) => {
    const d = shiftDay(first, i);
    if (d > today) return h("span", { class: "hm future" });
    const a = state.activity[d] || {};
    const score = (a.v ? 1 : 0) + (a.l || 0) + 2 * (a.t || 0);
    if (score) active++;
    const lvl = !score ? 0 : score === 1 ? 1 : score <= 3 ? 2 : score <= 6 ? 3 : 4;
    return h("span", { class: `hm l${lvl}${d === today ? " today" : ""}`, title: `${dateLabel(noon(d))}: ${describe(a)}` });
  });
  const st = account.user ? streak() : null;
  return h("section", { class: "card" }, h("h3", {}, t("path_activity")),
    h("div", { class: "heatmap", role: "img", "aria-label": t("path_days", { n: active }) }, cells),
    h("div", { class: "hm-legend small muted" }, h("span", {}, t("path_days", { n: active })), h("span", { class: "spacer" }),
      t("path_less"), [0, 1, 2, 3, 4].map((l) => h("span", { class: `hm l${l}` })), t("path_more")),
    st ? h("p", { class: "streak-line" }, star(), h("b", {}, t("streak_n", { n: st.count })), h("span", { class: "muted" }, ` · ${t("streak_best", { n: st.best })}`))
      : h("p", { class: "small muted", style: { marginTop: "10px" } }, t("path_guest")));
}

function milestonesCard(steps, pct) {
  const learned = Object.values(state.learned || {});
  const best = account.user ? streak().best : 0;
  const list = [
    ["bookOpen", "ms_lesson", learned.some((x) => (x.done || []).length)],
    ["check", "ms_test", learned.some((x) => Object.keys(x.chapters || {}).length || x.final)],
    ["award", "ms_cert", Object.keys(state.certs || {}).length > 0],
    ["route", "ms_half", pct >= 50],
    ["grad", "ms_done", steps.length > 0 && steps.every((x) => x.done)],
    [null, "ms_s7", best >= 7],
    [null, "ms_s30", best >= 30],
  ];
  return h("section", { class: "card" }, h("h3", {}, t("path_milestones")),
    h("div", { class: "milestones" }, list.map(([ic, key, got]) => h("div", { class: `ms${got ? " got" : ""}` },
      h("span", { class: "ms-ico" }, ic ? icon(ic) : star()), h("span", {}, t(key))))));
}

// ---------------------------------------------------------------- the streak star in the header
export function renderStreak() {
  const box = $("streak");
  if (!box) return;
  if (!account.user) { box.replaceChildren(); return; }
  const st = streak();
  const toggle = (e) => { e.stopPropagation(); state.streakOpen = !state.streakOpen; state.accountOpen = false; renderStreak(); };
  const button = h("button", { type: "button", class: "streak-btn", "aria-expanded": String(!!state.streakOpen), "aria-label": t("streak_aria", { n: st.count }),
    title: t("streak_n", { n: st.count }), onclick: toggle }, star(), h("b", {}, String(st.count)));
  const today = dayKey();
  const week = Array.from({ length: 7 }, (_, i) => shiftDay(today, i - 6));
  const pop = state.streakOpen ? h("div", { class: "streak-pop", role: "dialog", "aria-label": t("streak_n", { n: st.count }), onclick: (e) => e.stopPropagation() },
    h("div", { class: "sp-head" }, star("star big"), h("div", {}, h("b", {}, t("streak_n", { n: st.count })), h("div", { class: "small muted" }, t("streak_best", { n: st.best })))),
    h("div", { class: "sp-week" }, week.map((d) => h("span", { class: `sp-day${state.activity[d]?.v ? " on" : ""}${d === today ? " today" : ""}` }, star(),
      h("span", {}, new Date(noon(d)).toLocaleDateString(LOCALES[state.lang], { weekday: "narrow" }))))),
    st.ended >= 2 ? h("p", { class: "sp-ended small" }, t("streak_ended", { n: st.ended })) : null,
    h("p", { class: "small muted sp-rule" }, t("streak_rule")),
    h("a", { class: "btn btn-secondary btn-sm btn-block", href: "#/path", onclick: () => { state.streakOpen = false; renderStreak(); } }, t("streak_open"))) : null;
  box.replaceChildren(...[button, pop].filter(Boolean));
}
document.addEventListener("click", () => { if (state.streakOpen) { state.streakOpen = false; renderStreak(); } });
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && state.streakOpen) { state.streakOpen = false; renderStreak(); } });
