// Learn tab: full open courses — catalog, course overview, lesson player, chapter tests, final test and Path.AI certificates.
import { h, s, trendSpan } from "./charts.js";
import { BRAND } from "./brand.js";
import { state, store, t, api, loc, skillName, roleTitle, hasProfile, sdgBadge, icon, rerender, go, toast,
  ensureRadar, ensureMatches, ensureCourses, dateLabel, goalOf, logActivity, masterSkill } from "./core.js";

const CATS = ["all", "ai_data", "digital", "green", "human"];
const CAT_ICON = { ai_data: "cpu", digital: "code", green: "leaf", human: "users" };
const SKILL_ICON = {
  python: "code", sql: "database", data_analysis: "search", data_viz: "pie", statistics: "sigma", machine_learning: "cpu", genai_apps: "sparkles",
  prompt_eng: "message", mlops: "rocket", data_engineering: "flow", ai_governance: "shield", computer_vision: "eye", excel: "grid",
  digital_literacy: "globe", software_dev: "layout", cloud_devops: "cloud", linux_networking: "terminal", cybersecurity: "lock", ux_design: "pen",
  process_automation: "bot", iot_embedded: "wifi", digital_marketing: "megaphone", solar_pv: "sun", energy_efficiency: "bolt", esg_reporting: "file",
  carbon_accounting: "factory", ev_tech: "car", precision_agri: "sprout", gis: "map", circular_economy: "refresh", electrical: "plug",
  communication: "chat", customer_service: "headset", project_mgmt: "clipboard", leadership: "users", analytical_thinking: "target",
  creative_thinking: "bulb", teaching_training: "grad", bookkeeping: "calc", data_entry: "keyboard", graphic_design: "palette",
  healthcare_basics: "heart", lifelong_learning: "bookOpen", finance_domain: "trend", supply_chain: "route", lean_quality: "check",
  industrial_automation: "factory", content_writing: "pen", sales: "briefcase", hr_people: "users", compliance_risk: "shield",
  product_mgmt: "layers", entrepreneurship: "rocket",
};
const courseIcon = (c) => icon(SKILL_ICON[c.skill] || CAT_ICON[c.category] || "book");
const LETTERS = "ABCDE";

// ---------------------------------------------------------------- progress (kept in this browser only)
// { done: [lesson ids], last, at, chapters: { "1": { token, score, total } }, final: { token, score, total } }
// The tokens are signed by the server: the final test is only handed out against a pass for every chapter.
const progressOf = (sid) => state.learned[sid] || { done: [] };

function saveProgress(sid, patch) {
  state.learned[sid] = { ...progressOf(sid), ...patch, at: Date.now() };
  store.set("learned", state.learned);
}

function markDone(sid, lid) {
  const p = progressOf(sid);
  if (p.done.includes(lid)) return;
  saveProgress(sid, { done: [...p.done, lid] });
  const lesson = state.course?.skill === sid ? state.course.syllabus.flatMap((m) => m.lessons).find((l) => l.id === lid) : null;
  logActivity("l", 1, lesson?.minutes || 0);                  // for My path: the day's lessons and minutes
}

const pctDone = (sid, total) => (total ? Math.round((Math.min(progressOf(sid).done.length, total) / total) * 100) : 0);
const certified = (sid) => !!state.certs[sid];
const chapterPass = (sid, n) => progressOf(sid).chapters?.[n] || null;
const chaptersPassed = (sid, count) => Array.from({ length: count }, (_, i) => i + 1).filter((n) => chapterPass(sid, n)).length;
// chapter n (1-based) opens once the test of chapter n − 1 is passed
const chapterOpen = (c, n) => n <= 1 || certified(c.skill) || !!chapterPass(c.skill, n - 1);
const finalOpen = (c) => certified(c.skill) || chaptersPassed(c.skill, c.syllabus.length) === c.syllabus.length;
const chapterOfLesson = (c, lid) => c.syllabus.findIndex((m) => m.lessons.some((l) => l.id === lid)) + 1;
export const testHref = (sid, part) => `#/learn/${sid}/${part === "final" ? "final" : `test-${part}`}`;

// "#/learn/<sid>/test-2" → 2 · ".../final" (and the older ".../test") → "final" · a lesson id → null
export function testPart(sub) {
  if (sub === "final" || sub === "test") return "final";
  const m = /^test-(\d+)$/.exec(sub || "");
  return m ? Number(m[1]) : null;
}

// Where "continue" should take the learner: the first unread lesson of the current chapter, else its test.
export function nextStep(c) {
  const done = new Set(progressOf(c.skill).done);
  for (const [i, m] of c.syllabus.entries()) {
    if (chapterPass(c.skill, i + 1)) continue;
    const lesson = m.lessons.find((l) => !done.has(l.id));
    return lesson ? { kind: "lesson", n: i + 1, lesson } : { kind: "test", n: i + 1 };
  }
  return { kind: "final" };
}

const chapterEntry = (c, n) => {
  const done = new Set(progressOf(c.skill).done);
  const lesson = c.syllabus[n - 1].lessons.find((l) => !done.has(l.id));
  return lesson ? `#/learn/${c.skill}/${lesson.id}` : testHref(c.skill, n);
};

export function hoursLabel(minutes) {
  if (minutes < 60) return t("minutes_n", { n: minutes });
  return t("hours_n", { h: String(Math.round(minutes / 6) / 10) });
}

const catColor = (cat) => ({ "--fam": `var(--fam-${cat})` });

// ---------------------------------------------------------------- data
export async function ensureLearn(route) {
  await ensureCourses();
  if (route.name === "certificate") {
    if (state.certViewToken !== route.arg) {
      state.certView = await api(`/api/certificates/verify/${encodeURIComponent(route.arg || "")}`);
      state.certViewToken = route.arg;
    }
    return;
  }
  const sid = route.arg;
  if (!sid) {
    await ensureRadar();
    if (hasProfile()) await ensureMatches();
    return;
  }
  if (state.course?.skill !== sid) {
    state.course = await api(`/api/learn/course/${encodeURIComponent(sid)}`);
    state.outlineOpen = false;
  }
  const part = testPart(route.sub);
  if (part !== null) {
    if (state.quiz.key !== `${sid}/${part}`) await openTest(state.course, part);
  } else if (route.sub) {
    const key = `${sid}/${route.sub}`;
    if (state.lesson?.key !== key) {
      state.lesson = { key, ...(await api(`/api/learn/course/${encodeURIComponent(sid)}/lesson/${encodeURIComponent(route.sub)}`)) };
      state.outlineOpen = false;
    }
    saveProgress(sid, { last: route.sub });
  }
}

// ---------------------------------------------------------------- catalog
function cover(c) {
  return h("div", { class: "cover", style: catColor(c.category) },
    h("span", { class: "cover-cat" }, loc(state.meta.categories[c.category])),
    h("span", { class: "cover-icon" }, courseIcon(c)),
    h("span", { class: "cover-level" }, t(`level_${c.level.toLowerCase()}`)));
}

function courseCard(c, trend) {
  const cert = state.certs[c.skill];
  const p = pctDone(c.skill, c.lessons);
  return h("a", { class: "ccard", href: `#/learn/${c.skill}`, style: catColor(c.category) },
    cover(c),
    h("div", { class: "ccard-body" },
      h("h3", {}, c.title),
      h("p", { class: "ccard-sub" }, c.subtitle),
      h("div", { class: "ccard-meta" },
        h("span", {}, icon("book"), t("lessons_n", { n: c.lessons })),
        h("span", {}, icon("clock"), hoursLabel(c.minutes)),
        trend ? trendSpan(trend.pct, ` ${t("per_year")}`) : null),
      p && !cert ? h("div", { class: "pbar", role: "img", "aria-label": t("progress_pct", { p }) }, h("span", { style: { width: `${p}%` } })) : null,
      h("div", { class: "ccard-foot" },
        h("span", { class: "ccard-provider" }, c.providers > 1 ? `${c.provider} ${t("plus_more", { n: c.providers - 1 })}` : c.provider),
        cert ? h("span", { class: "badge robust" }, `✓ ${t("certified")}`) : p ? h("span", { class: "badge" }, t("progress_pct", { p })) : null)));
}

function resumeCard(c) {
  const p = progressOf(c.skill);
  const pct = pctDone(c.skill, c.lessons);
  return h("a", { class: "resume-card", href: p.last ? `#/learn/${c.skill}/${p.last}` : `#/learn/${c.skill}`, style: catColor(c.category) },
    h("span", { class: "ri" }, courseIcon(c)),
    h("span", { class: "rt" }, h("b", {}, c.title), h("span", { class: "small muted" },
      t("resume_meta", { done: Math.min(p.done.length, c.lessons), n: c.lessons, d: chaptersPassed(c.skill, c.chapters), m: c.chapters }))),
    h("span", { class: "ring sm", style: { "--p": pct } }, h("span", {}, `${pct}%`)));
}

function recommendation() {
  if (!hasProfile() || !state.matches?.roles?.length) return null;
  const top = state.matches.roles[0];
  const ids = top.items.filter((i) => i.status !== "have").sort((a, b) => b.weight - a.weight).map((i) => i.id);
  const picks = ids.map((id) => state.courses.find((c) => c.skill === id)).filter(Boolean).slice(0, 3);
  return picks.length ? { role: top.id, picks } : null;
}

function matchesFilter(c, f) {
  const q = f.q.trim().toLowerCase();
  return (f.cat === "all" || c.category === f.cat)
    && (!q || [c.title, c.subtitle, c.provider, skillName(c.skill)].some((s) => s.toLowerCase().includes(q)));
}

export function viewLearn() {
  const trend = Object.fromEntries((state.radar?.skills || []).map((s) => [s.id, s]));
  const all = state.courses;
  const f = state.learnFilter;
  const totals = { lessons: all.reduce((a, c) => a + c.lessons, 0), hours: Math.round(all.reduce((a, c) => a + c.minutes, 0) / 60) };
  const inProgress = all.filter((c) => progressOf(c.skill).done.length && !state.certs[c.skill])
    .sort((a, b) => (progressOf(b.skill).at || 0) - (progressOf(a.skill).at || 0)).slice(0, 3);
  const rec = recommendation();
  const certs = Object.entries(state.certs);
  const counts = Object.fromEntries(CATS.map((cat) => [cat, cat === "all" ? all.length : all.filter((c) => c.category === cat).length]));

  const grid = h("div", { class: "course-grid" });
  const fillGrid = () => {
    const shown = all.filter((c) => matchesFilter(c, f));
    grid.replaceChildren(...(shown.length ? shown.map((c) => courseCard(c, trend[c.skill]))
      : [h("p", { class: "empty" }, t("no_results", { q: f.q }))]));
  };
  fillGrid();
  const search = h("input", { type: "search", placeholder: t("search_courses"), "aria-label": t("search_courses"), value: f.q,
    oninput: (e) => { f.q = e.target.value; fillGrid(); } });

  return h("div", {},
    h("section", { class: "page-head" }, h("div", { class: "container" },
      h("h1", {}, t("learn_title")),
      h("p", {}, t("learn_sub")),
      h("div", { class: "hero-stats" },
        h("div", {}, h("b", {}, String(all.length)), h("span", {}, t("stat_courses"))),
        h("div", {}, h("b", {}, String(totals.lessons)), h("span", {}, t("stat_lessons"))),
        h("div", {}, h("b", {}, `${totals.hours} h`), h("span", {}, t("stat_hours"))),
        h("div", {}, h("b", {}, "100%"), h("span", {}, t("stat_open")))))),
    h("div", { class: "container learn-body" },
      inProgress.length ? h("section", {}, h("div", { class: "sec-head" }, h("h2", {}, t("continue_t"))),
        h("div", { class: "rail" }, inProgress.map(resumeCard))) : null,
      certs.length ? h("section", {}, h("div", { class: "sec-head" }, h("h2", {}, t("my_certs"))),
        h("div", { class: "cert-chips" }, certs.map(([sid, c]) => h("a", { class: "cert-chip", href: `#/certificate/${c.token}` },
          icon("award"), h("span", {}, all.find((x) => x.skill === sid)?.title || skillName(sid)), h("span", { class: "tiny" }, dateLabel(c.date)))))) : null,
      rec ? h("section", {}, h("div", { class: "sec-head" }, h("h2", {}, t("recommended", { role: roleTitle(rec.role) }))),
        h("div", { class: "course-grid" }, rec.picks.map((c) => courseCard(c, trend[c.skill])))) : null,
      h("section", {},
        h("div", { class: "sec-head" }, h("h2", {}, t("all_courses"))),
        h("div", { class: "toolbar" },
          h("div", { class: "seg-tabs", role: "tablist", "aria-label": t("all_courses") }, CATS.map((cat) => h("button", {
            type: "button", role: "tab", "aria-selected": String(f.cat === cat), class: f.cat === cat ? "on" : "",
            onclick: () => { f.cat = cat; rerender(); } },
          cat === "all" ? t("cat_all") : loc(state.meta.categories[cat]), h("span", { class: "n" }, String(counts[cat]))))),
          h("div", { class: "search compact" }, icon("search"), search)),
        grid),
      h("p", { class: "source-line" }, t("learn_license"))));
}

// ---------------------------------------------------------------- course overview
function chip(ic, text) {
  return h("span", {}, icon(ic), text);
}

function lessonNumber(c, lid) {
  return c.syllabus.flatMap((m) => m.lessons).findIndex((l) => l.id === lid) + 1;
}

function primaryAction(c, cls = "btn btn-primary btn-lg") {
  const cert = state.certs[c.skill];
  const p = progressOf(c.skill);
  if (cert) return h("a", { class: cls, href: `#/certificate/${cert.token}` }, icon("award"), t("view_cert"));
  if (p.final) return h("a", { class: cls, href: testHref(c.skill, "final") }, icon("award"), t("get_cert_cta"));
  const step = nextStep(c);
  if (step.kind === "final") return h("a", { class: cls, href: testHref(c.skill, "final") }, t("take_test"), " →");
  if (step.kind === "test") return h("a", { class: cls, href: testHref(c.skill, step.n) }, t("take_chapter_test", { n: step.n }), " →");
  if (!p.done.length) return h("a", { class: cls, href: `#/learn/${c.skill}/${step.lesson.id}` }, t("start_course"), " →");
  return h("a", { class: cls, href: `#/learn/${c.skill}/${step.lesson.id}` }, t("resume_course", { n: lessonNumber(c, step.lesson.id) }), " →");
}

function chapterTestRow(c, n, open, pass) {
  const rule = c.tests.chapter;
  const last = n === c.syllabus.length;
  return h("div", { class: `ctest ${pass ? "done" : ""} ${open ? "" : "locked"}` },
    h("span", { class: "ct-ico" }, icon(pass ? "check" : open ? "award" : "lock")),
    h("span", { class: "lt" }, h("b", {}, t("chapter_test", { n })),
      h("span", { class: "small muted" }, t(last ? "ctest_rule_last" : "ctest_rule", { q: rule.questions, p: rule.pass }))),
    pass ? h("span", { class: "badge robust" }, `✓ ${t("test_passed", { s: pass.score, n: pass.total })}`)
      : open ? h("a", { class: "btn btn-primary btn-sm", href: testHref(c.skill, n) }, t("take_test_short"))
        : h("span", { class: "badge muted-badge" }, icon("lock"), t("locked")));
}

function moduleBlock(c, m, i, done, openIndex) {
  const n = i + 1;
  const open = chapterOpen(c, n);
  const pass = chapterPass(c.skill, n);
  const doneHere = m.lessons.filter((l) => done.has(l.id)).length;
  return h("details", { class: `module ${open ? "" : "locked"}`, open: i === openIndex },
    h("summary", {},
      h("span", { class: `mod-n ${pass ? "done" : open ? "" : "locked"}` }, pass ? icon("check") : open ? String(n) : icon("lock")),
      h("span", { class: "mod-t" }, h("b", {}, m.title),
        h("span", { class: "small muted" }, [t("lessons_n", { n: m.lessons.length }), hoursLabel(m.minutes),
          open ? `${doneHere}/${m.lessons.length}` : t("chapter_locked_short", { m: n - 1 })].join(" · "))),
      h("span", { class: "mod-chev" }, icon("chevron"))),
    h("ol", { class: "lesson-list" },
      m.lessons.map((l) => h("li", {}, open
        ? h("a", { href: `#/learn/${c.skill}/${l.id}`, class: done.has(l.id) ? "done" : "" },
          h("span", { class: "st" }, done.has(l.id) ? icon("check") : icon("play")),
          h("span", { class: "lt" }, l.title),
          h("span", { class: "lm" }, t("minutes_n", { n: l.minutes })))
        : h("span", { class: "locked-row" },
          h("span", { class: "st" }, icon("lock")),
          h("span", { class: "lt" }, l.title),
          h("span", { class: "lm" }, t("minutes_n", { n: l.minutes }))))),
      h("li", {}, chapterTestRow(c, n, open, pass))));
}

function finalCard(c) {
  const cert = state.certs[c.skill];
  const p = progressOf(c.skill);
  const open = finalOpen(c);
  const rule = c.tests.final;
  const passed = chaptersPassed(c.skill, c.syllabus.length);
  return h("section", { class: `card test-card ${open ? "" : "locked"}` },
    h("span", { class: "ti" }, icon(open ? "award" : "lock")),
    h("div", {}, h("h3", {}, t("test_card_t")),
      h("p", { class: "small", style: { marginTop: "4px" } }, t("test_card_d", { n: rule.questions, p: rule.pass })),
      open ? null : h("p", { class: "small muted", style: { marginTop: "6px" } }, t("final_locked_d", { n: c.syllabus.length, d: passed }))),
    cert ? h("a", { class: "btn btn-secondary", href: `#/certificate/${cert.token}` }, t("view_cert"))
      : p.final ? h("a", { class: "btn btn-primary", href: testHref(c.skill, "final") }, icon("award"), t("get_cert_cta"))
        : open ? h("a", { class: "btn btn-primary", href: testHref(c.skill, "final") }, t("take_test"))
          : h("button", { type: "button", class: "btn btn-secondary", disabled: true }, icon("lock"), t("locked")));
}

function upNext(c) {
  const p = progressOf(c.skill);
  if (state.certs[c.skill] || p.final) return null;
  const step = nextStep(c);
  const label = step.kind === "lesson" ? (p.done.length ? t("up_next") : t("first_lesson")) : t("up_next");
  const title = step.kind === "lesson" ? step.lesson.title : step.kind === "test" ? t("chapter_test", { n: step.n }) : t("final_test");
  return h("div", { class: "next" }, h("span", {}, label), title);
}

export function viewCourse() {
  const c = state.course;
  const p = progressOf(c.skill);
  const done = new Set(p.done);
  const cert = state.certs[c.skill];
  const pct = pctDone(c.skill, c.lessons);
  const current = c.syllabus.findIndex((_, i) => !chapterPass(c.skill, i + 1));
  const openIndex = cert ? -1 : current;
  const passed = chaptersPassed(c.skill, c.syllabus.length);
  const trend = state.radar?.skills?.find((s) => s.id === c.skill);
  const nc = c.sources.some((s) => s.noncommercial);
  return h("div", {},
    h("section", { class: "course-hero", style: catColor(c.category) }, h("div", { class: "container ch-grid" },
      h("div", {},
        h("nav", { class: "crumbs", "aria-label": t("crumb_learn") }, h("a", { href: "#/learn" }, t("crumb_learn")), h("span", { "aria-hidden": "true" }, "/"),
          h("span", {}, loc(state.meta.categories[c.category]))),
        h("h1", {}, c.title),
        h("p", { class: "lead" }, c.subtitle),
        h("div", { class: "ch-chips" },
          chip("layers", t(`level_${c.level.toLowerCase()}`)),
          chip("book", t("lessons_n", { n: c.lessons })),
          chip("clock", hoursLabel(c.minutes)),
          chip("check", t("chip_ctests", { n: c.syllabus.length })),
          chip("award", t("chip_test", { n: c.tests.final.questions })),
          chip("grad", t("chip_cert"))),
        h("div", { class: "ch-cta" }, primaryAction(c),
          h("a", { class: "btn btn-ghost btn-lg", href: "#syllabus", onclick: (e) => { e.preventDefault(); document.getElementById("syllabus")?.scrollIntoView({ behavior: "smooth" }); } },
            t("view_syllabus"))),
        h("p", { class: "ch-provider" }, t("built_from"), " ", c.sources.map((s) => s.name).join(" · "))),
      h("aside", { class: "ch-card", "aria-label": t("your_progress") },
        h("div", { class: "top" }, h("span", { class: "ring", style: { "--p": pct } }, h("span", {}, `${pct}%`)),
          h("div", {}, h("b", {}, t("your_progress")),
            h("span", { class: "small muted" }, cert ? `✓ ${t("certified")} · ${dateLabel(cert.date)}`
              : t("lessons_done", { done: Math.min(p.done.length, c.lessons), n: c.lessons })),
            cert ? null : h("span", { class: "small muted" }, t("ctests_done", { d: passed, n: c.syllabus.length })))),
        upNext(c),
        primaryAction(c, "btn btn-primary btn-block"),
        trend ? h("p", { class: "tiny muted" }, t("demand_trend"), " ", trendSpan(trend.pct, ` ${t("per_year")}`)) : null))),
    h("div", { class: "container course-body" },
      h("div", { class: "cb-main" },
        h("section", { class: "card" }, h("h2", {}, t("outcomes_t")),
          h("ul", { class: "outcomes" }, c.outcomes.map((o) => h("li", {}, icon("check"), h("span", {}, o))))),
        h("section", { id: "syllabus" },
          h("div", { class: "syl-head" }, h("h2", {}, t("syllabus_t")),
            h("span", { class: "small muted" }, t("syllabus_meta", { m: c.syllabus.length, n: c.lessons, h: hoursLabel(c.minutes) }))),
          h("p", { class: "small muted syl-rule" }, icon("lock"), t("syllabus_rule", { q: c.tests.chapter.questions, p: c.tests.chapter.pass })),
          c.syllabus.map((m, i) => moduleBlock(c, m, i, done, openIndex))),
        finalCard(c)),
      h("aside", { class: "cb-side" },
        h("section", { class: "card" }, h("h3", {}, t("sources_t")), h("p", { class: "small muted", style: { marginTop: "4px" } }, t("sources_d")),
          h("ul", { class: "src-list" }, c.sources.map((s) => h("li", {},
            h("a", { href: s.url, target: "_blank", rel: "noopener" }, s.name),
            h("span", { class: "tiny muted" }, s.attribution),
            h("a", { class: `lic ${s.noncommercial ? "nc" : ""}`, href: s.license_url, target: "_blank", rel: "noopener" }, s.license))))),
        nc ? h("p", { class: "tiny muted" }, t("nc_note")) : null,
        c.sdgs.length ? h("section", { class: "card" }, h("h3", { style: { marginBottom: "10px" } }, t("sdg_t")),
          c.sdgs.map((s) => h("div", { class: "row", style: { gap: "10px", flexWrap: "nowrap", alignItems: "flex-start", marginTop: "8px" } },
            sdgBadge(s.goal, true, null, { skill: c.skill }), h("span", { class: "small" }, h("b", {}, `${s.target} `), s.why)))) : null,
        c.practice ? h("section", { class: "card" }, h("h3", {}, t("practice_t")), h("p", { class: "small", style: { marginTop: "6px" } }, c.practice)) : null)));
}

// A locked chapter (or the final test before every chapter is passed) explains what unlocks it.
function lockScreen(c, part) {
  const isFinal = part === "final";
  const rule = c.tests.chapter;
  // the button leads to where the learner actually is, which may be an earlier chapter than the one just before
  const step = nextStep(c);
  const go = step.kind === "lesson" ? { href: `#/learn/${c.skill}/${step.lesson.id}`, label: t("continue_chapter", { n: step.n }) }
    : step.kind === "test" ? { href: testHref(c.skill, step.n), label: t("take_chapter_test", { n: step.n }) }
      : { href: testHref(c.skill, "final"), label: t("take_test") };
  return h("div", { class: "test-wrap" },
    h("div", { class: "test-top" }, h("a", { class: "pt-back", href: `#/learn/${c.skill}` }, icon("arrowLeft"), h("span", {}, c.title))),
    h("div", { class: "lock-card" },
      h("span", { class: "lock-ico" }, icon("lock")),
      h("h2", {}, isFinal ? t("final_locked_h") : t("chapter_locked_h", { n: part, title: c.syllabus[part - 1]?.title || "" })),
      h("p", {}, isFinal ? t("final_locked_d", { n: c.syllabus.length, d: chaptersPassed(c.skill, c.syllabus.length) })
        : t("chapter_locked_d", { m: part - 1, p: rule.pass, q: rule.questions })),
      h("div", { class: "row", style: { justifyContent: "center" } },
        h("a", { class: "btn btn-primary", href: go.href }, go.label, " →"),
        h("a", { class: "btn btn-secondary", href: `#/learn/${c.skill}` }, t("back_course")))));
}

// ---------------------------------------------------------------- lesson player
// Lesson HTML is sanitised with an nh3 allowlist when courses are built (scripts/learnkit/convert.py). As a second
// line of defence it is parsed in an inert DOMParser document and re-filtered here before it reaches the page.
const HTML_TAGS = new Set(["P", "BR", "HR", "H2", "H3", "H4", "H5", "H6", "UL", "OL", "LI", "DL", "DT", "DD", "A", "IMG", "FIGURE", "FIGCAPTION",
  "TABLE", "THEAD", "TBODY", "TFOOT", "TR", "TH", "TD", "CAPTION", "BLOCKQUOTE", "PRE", "CODE", "EM", "STRONG", "B", "I", "U", "SUB", "SUP",
  "SMALL", "MARK", "KBD", "DEL", "INS", "S", "DIV", "SPAN", "DETAILS", "SUMMARY", "ABBR", "CITE", "Q"]);
const MATHML = "http://www.w3.org/1998/Math/MathML";
const MATH_TAGS = new Set(["math", "mrow", "mi", "mo", "mn", "ms", "mtext", "msup", "msub", "msubsup", "mfrac", "msqrt", "mroot", "mover", "munder",
  "munderover", "mtable", "mtr", "mtd", "mspace", "mstyle", "mpadded", "mphantom", "menclose", "semantics"]);
const SAFE_ATTRS = new Set(["href", "src", "alt", "title", "width", "height", "loading", "colspan", "rowspan", "scope", "start", "type", "class", "id",
  "target", "rel", "display", "stretchy", "fence", "separator", "form", "linethickness", "columnspan", "displaystyle", "scriptlevel"]);

function safeFragment(html) {
  const doc = new DOMParser().parseFromString(`<!doctype html><body>${html}`, "text/html");
  const clean = (node) => {
    for (const el of [...node.children]) {
      const allowed = el.namespaceURI === MATHML ? MATH_TAGS.has(el.localName) : HTML_TAGS.has(el.tagName);
      if (!allowed) { el.remove(); continue; }
      for (const attr of [...el.attributes]) {
        const name = attr.name.toLowerCase();
        const value = attr.value.trim();
        if (!SAFE_ATTRS.has(name) || ((name === "href" || name === "src") && !/^(https?:|mailto:|#)/i.test(value))) el.removeAttribute(attr.name);
      }
      if (el.tagName === "A" && el.getAttribute("target") === "_blank") el.setAttribute("rel", "noopener noreferrer");
      clean(el);
    }
  };
  clean(doc.body);
  const frag = document.createDocumentFragment();
  frag.append(...doc.body.childNodes);
  return frag;
}

function scrollToAnchor(hash) {
  const id = decodeURIComponent(hash.replace(/^#/, ""));
  const el = document.getElementById(id) || document.getElementById(`h-${id}`);
  if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
}

function inPageLinks(e) {
  const a = e.target.closest("a[href^='#']");
  if (!a || a.getAttribute("href").startsWith("#/")) return;
  e.preventDefault(); // in-page anchors must not hijack the hash router
  scrollToAnchor(a.getAttribute("href"));
}

function outline(c, lesson, done) {
  const close = () => { state.outlineOpen = false; rerender(); };
  const fin = finalOpen(c);
  return h("nav", { class: `player-outline ${state.outlineOpen ? "open" : ""}`, "aria-label": t("outline") },
    h("button", { type: "button", class: "btn btn-secondary btn-sm outline-close", onclick: close }, icon("close"), t("close")),
    h("p", { class: "po-title" }, t("outline")),
    c.syllabus.map((m, i) => {
      const n = i + 1;
      const open = chapterOpen(c, n);
      const pass = chapterPass(c.skill, n);
      return h("div", { class: `po-mod ${open ? "" : "locked"}` }, h("b", {}, `${n}. ${m.title}`),
        m.lessons.map((l) => (open
          ? h("a", { href: `#/learn/${c.skill}/${l.id}`, class: done.has(l.id) ? "done" : "", "aria-current": l.id === lesson.id ? "page" : null },
            h("span", { class: "dot" }, done.has(l.id) ? icon("check") : null), h("span", {}, l.title))
          : h("span", { class: "po-locked" }, h("span", { class: "dot" }, icon("lock")), h("span", {}, l.title)))),
        h(open ? "a" : "span", { class: `po-ctest ${pass ? "done" : ""} ${open ? "" : "locked"}`, href: open ? testHref(c.skill, n) : null },
          icon(pass ? "check" : open ? "award" : "lock"), h("span", {}, t("chapter_test", { n })), pass ? h("span", { class: "tiny" }, `${pass.score}/${pass.total}`) : null));
    }),
    h(fin ? "a" : "span", { class: `po-test ${fin ? "" : "locked"}`, href: fin ? testHref(c.skill, "final") : null }, icon(fin ? "award" : "lock"), t("final_test")));
}

export function viewLesson() {
  const c = state.course;
  const L = state.lesson;
  const n = chapterOfLesson(c, L.id);
  if (!chapterOpen(c, n)) return lockScreen(c, n);
  const done = new Set(progressOf(c.skill).done);
  const chapter = c.syllabus[n - 1];
  const lastOfChapter = chapter.lessons[chapter.lessons.length - 1].id === L.id;
  const after = !lastOfChapter ? { href: `#/learn/${c.skill}/${L.next}`, label: t("complete_next") }
    : !chapterPass(c.skill, n) && !certified(c.skill) ? { href: testHref(c.skill, n), label: t("complete_chapter_test", { n }) }
      : L.next ? { href: `#/learn/${c.skill}/${L.next}`, label: t("complete_next") }
        : { href: certified(c.skill) ? `#/learn/${c.skill}` : testHref(c.skill, "final"), label: certified(c.skill) ? t("complete_next") : t("complete_test") };
  const pct = pctDone(c.skill, c.lessons);
  const prose = h("div", { class: "lesson-prose" }, safeFragment(L.html));
  prose.addEventListener("click", inPageLinks);
  const toc = L.toc.filter((x) => x.level <= 3);
  const complete = () => {
    markDone(c.skill, L.id);
    go(after.href);
  };
  return h("div", {},
    h("div", { class: "player-top" }, h("div", { class: "pt-inner" },
      h("a", { class: "pt-back", href: `#/learn/${c.skill}` }, icon("arrowLeft"), h("span", {}, c.title)),
      h("div", { class: "pt-progress" }, h("div", { class: "pbar", role: "img", "aria-label": t("progress_pct", { p: pct }) }, h("span", { style: { width: `${pct}%` } })),
        h("span", { class: "tiny muted num" }, `${L.index}/${L.count}`)),
      h("button", { type: "button", class: "btn btn-secondary btn-sm pt-outline-btn", "aria-expanded": String(!!state.outlineOpen),
        onclick: () => { state.outlineOpen = !state.outlineOpen; rerender(); } }, icon("list"), t("outline")))),
    state.outlineOpen ? h("div", { class: "outline-scrim", onclick: () => { state.outlineOpen = false; rerender(); } }) : null,
    h("div", { class: "player" },
      outline(c, L, done),
      h("article", { class: "player-main" },
        h("header", { class: "lesson-head" },
          h("span", { class: "eyebrow" }, `${t("chapter_n", { n })} · ${L.module} · ${t("lesson_x_of_y", { n: L.index, total: L.count })}`),
          h("h1", {}, L.title),
          h("div", { class: "lesson-meta" },
            h("span", {}, icon("clock"), t("read_time", { m: L.minutes })),
            h("span", {}, icon("book"), L.source.name),
            h("a", { href: L.source.license_url, target: "_blank", rel: "noopener" }, icon("shield"), L.source.license),
            done.has(L.id) ? h("span", { class: "pb-status" }, icon("check"), t("completed")) : null)),
        prose,
        h("footer", { class: "lesson-source" }, icon("shield"),
          h("div", {},
            h("p", {}, t("lesson_source_1"), " ", h("a", { href: L.source.url, target: "_blank", rel: "noopener" }, L.source.name), " · ",
              h("a", { href: L.source.license_url, target: "_blank", rel: "noopener" }, L.source.license), "."),
            h("p", { class: "tiny" }, L.source.attribution, ". ", h("a", { href: L.original_url, target: "_blank", rel: "noopener" }, `${t("view_original")} ↗`))))),
      toc.length > 1 ? h("aside", { class: "player-toc", "aria-label": t("on_this_page") }, h("p", { class: "po-title" }, t("on_this_page")),
        toc.map((x) => h("a", { href: `#${x.id}`, class: x.level === 3 ? "sub" : "", onclick: (e) => { e.preventDefault(); scrollToAnchor(x.id); } }, x.text))) : null),
    h("div", { class: "player-bar" }, h("div", { class: "pb-inner" },
      L.prev ? h("a", { class: "btn btn-secondary", href: `#/learn/${c.skill}/${L.prev}` }, "← ", t("prev")) : h("span"),
      h("span", { class: "pb-status small" }, done.has(L.id) ? `✓ ${t("completed")}` : ""),
      h("button", { type: "button", class: "btn btn-primary", onclick: complete }, after.label, " →"))));
}

// ---------------------------------------------------------------- chapter tests & final test
// Every attempt is a fresh random draw from the course's question pool, signed by the server; a retake passes the
// previous attempt along so it asks questions the learner has not just seen.
async function openTest(c, part, previous = null) {
  const Q = { key: `${c.skill}/${part}`, part, data: null, answers: [], idx: 0, result: null, error: null, locked: false,
    name: store.get("certName", ""), busy: false };
  state.quiz = Q;
  const p = progressOf(c.skill);
  if (part === "final" ? !finalOpen(c) : !chapterOpen(c, part)) { Q.locked = true; return; }
  if (part === "final" && p.final && !certified(c.skill)) { // passed earlier, certificate not claimed yet
    Q.result = { kind: "final", passed: true, score: p.final.score, total: p.final.total, token: p.final.token, results: [], review: [] };
    return;
  }
  try {
    Q.data = await api(`/api/learn/course/${encodeURIComponent(c.skill)}/test`, part === "final"
      ? { chapters: Object.values(p.chapters || {}).map((x) => x.token), previous }
      : { chapter: part, previous });
  } catch (e) { Q.error = String(e.message || e); }
}

async function submitTest(c) {
  const Q = state.quiz;
  Q.busy = true;
  rerender();
  try {
    const r = await api(`/api/learn/course/${encodeURIComponent(c.skill)}/test/grade`,
      { attempt: Q.data.attempt, answers: Q.data.questions.map((_, i) => (Number.isInteger(Q.answers[i]) ? Q.answers[i] : null)) });
    Q.result = r;
    if (r.passed) {
      const record = { token: r.token, score: r.score, total: r.total };
      if (r.kind === "chapter") saveProgress(c.skill, { chapters: { ...(progressOf(c.skill).chapters || {}), [r.chapter]: record } });
      else saveProgress(c.skill, { final: record });
      logActivity("t");
      if (r.kind !== "chapter" && masterSkill(c.skill)) toast(t("skill_raised", { skill: skillName(c.skill) }));
    }
    window.scrollTo({ top: 0 });
  } catch (e) { toast(String(e.message || e)); }
  Q.busy = false;
  rerender();
}

async function retakeTest(c) {
  const Q = state.quiz;
  Q.busy = true;
  rerender();
  await openTest(c, Q.part, Q.data?.attempt || null);
  rerender();
  window.scrollTo({ top: 0 });
}

async function createCertificate(c) {
  const Q = state.quiz;
  Q.busy = true;
  rerender();
  try {
    const { certificate } = await api(`/api/learn/course/${encodeURIComponent(c.skill)}/certificate`, { token: Q.result.token, name: Q.name });
    state.certs[c.skill] = { token: certificate.token, id: certificate.id, date: certificate.date, score: certificate.score, total: certificate.total };
    store.set("certs", state.certs);
    store.set("certName", Q.name);
    Q.busy = false;
    go(`#/certificate/${certificate.token}`);
    return;
  } catch (e) { toast(String(e.message || e)); }
  Q.busy = false;
  rerender();
}

function reviewLessons(c, r) {
  if (!r.review.length) return null;
  return [h("p", { class: "small review-h" }, r.passed ? t("worth_review") : t("review_these")),
    h("ul", { class: "review-list" }, r.review.map((l) => h("li", {},
      h("a", { href: `#/learn/${c.skill}/${l.id}` }, icon("book"), h("span", {}, l.title)))))];
}

// What the learner answered, right or wrong — without the key, which is revealed only after the final test is passed.
function yourAnswers(Q) {
  if (!Q.data || !Q.result.results.some((r) => !r.correct)) return null;
  return [h("h3", { class: "answers-h" }, t("your_answers")),
    h("p", { class: "small muted" }, t("answers_hidden")),
    h("div", { class: "answers" }, Q.data.questions.map((q, i) => {
      const res = Q.result.results[i];
      return h("div", { class: `answer-item ${res.correct ? "right" : "wrong"}` },
        h("p", {}, h("span", { class: res.correct ? "ok" : "bad" }, res.correct ? "✓ " : "✗ "), h("b", {}, q.q)),
        h("p", { class: "key" }, `${t("your_answer")}: `, q.options[Q.answers[i]] ?? "—"));
    }))];
}

function testResult(c) {
  const Q = state.quiz;
  const r = Q.result;
  const isFinal = r.kind === "final";
  const pct = Math.round((r.score / r.total) * 100);
  const ring = h("span", { class: "ring lg", style: { "--p": pct } }, h("span", {}, `${r.score}/${r.total}`));
  const backBtn = h("a", { class: "btn btn-secondary", href: `#/learn/${c.skill}` }, t("back_course"));
  if (!r.passed) {
    return h("div", { class: "test-wrap" },
      h("div", { class: "result fail" }, ring,
        h("h2", {}, r.score >= r.pass_mark - 1 ? t("failed_h") : t("not_yet_h")),
        h("p", {}, t(isFinal ? "failed_d" : "ch_failed_d", { s: r.score, n: r.total, p: r.pass_mark })),
        reviewLessons(c, r),
        h("div", { class: "row", style: { justifyContent: "center", marginTop: "8px" } },
          h("button", { type: "button", class: "btn btn-primary", disabled: Q.busy, onclick: () => retakeTest(c) }, icon("refresh"), t("retake_test")), backBtn)),
      yourAnswers(Q));
  }
  if (!isFinal) {
    const n = r.chapter;
    const next = c.syllabus[n];
    return h("div", { class: "test-wrap" },
      h("div", { class: "result pass" }, ring,
        h("h2", {}, t("ch_passed_h", { n })),
        h("p", {}, next ? t("ch_passed_next", { n: n + 1, title: next.title }) : t("ch_passed_last")),
        h("div", { class: "row", style: { justifyContent: "center", marginTop: "4px" } },
          next ? h("a", { class: "btn btn-primary", href: chapterEntry(c, n + 1) }, t("start_chapter", { n: n + 1 }), " →")
            : h("a", { class: "btn btn-primary", href: testHref(c.skill, "final") }, t("take_test"), " →"),
          backBtn),
        reviewLessons(c, r)),
      yourAnswers(Q));
  }
  const cert = state.certs[c.skill];
  return h("div", { class: "test-wrap" },
    h("div", { class: "result pass" }, ring,
      h("h2", {}, t("passed_h")),
      h("p", {}, t("passed_d", { s: r.score, n: r.total })),
      cert ? h("a", { class: "btn btn-secondary", href: `#/certificate/${cert.token}` }, icon("award"), t("view_cert")) : null,
      h("form", { class: "cert-form", onsubmit: (e) => { e.preventDefault(); createCertificate(c); } },
        h("label", { class: "field-label" }, t("cert_name"),
          h("input", { type: "text", class: "text-input", maxlength: 60, autocomplete: "name", required: true, value: Q.name,
            oninput: (e) => { Q.name = e.target.value; } })),
        h("button", { type: "submit", class: "btn btn-primary btn-block", disabled: Q.busy }, icon("award"), Q.busy ? t("cert_creating") : t("get_cert")),
        h("p", { class: "tiny muted" }, t("cert_privacy")))),
    Q.data ? [h("h3", { class: "answers-h" }, t("review_answers")),
      h("div", { class: "answers" }, Q.data.questions.map((q, i) => {
        const res = r.results[i];
        return h("div", { class: `answer-item ${res.correct ? "right" : "wrong"}` },
          h("p", {}, h("span", { class: res.correct ? "ok" : "bad" }, res.correct ? "✓ " : "✗ "), h("b", {}, q.q)),
          h("p", { class: "key" }, `${t("correct_answer")}: `, h("b", {}, q.options[res.answer])),
          res.explain ? h("p", { class: "small muted", style: { marginTop: "4px" } }, res.explain) : null,
          res.evidence ? h("blockquote", {}, `“${res.evidence}” — `, h("a", { href: `#/learn/${c.skill}/${q.lesson}` }, q.lesson_title)) : null);
      }))] : null);
}

let keysBound = false;
function bindTestKeys() {
  if (keysBound) return;
  keysBound = true;
  document.addEventListener("keydown", (e) => {
    const Q = state.quiz;
    if (!/\/learn\/[a-z_]+\/(test-\d+|final|test)$/.test(location.hash) || !Q?.data || Q.result || Q.busy
      || e.target.closest("input, textarea") || e.metaKey || e.ctrlKey || e.altKey) return;
    const q = Q.data.questions[Q.idx];
    const n = Number(e.key);
    if (n >= 1 && n <= q.options.length) { Q.answers[Q.idx] = n - 1; rerender(); }
    else if (e.key === "Enter" && Number.isInteger(Q.answers[Q.idx])) {
      e.preventDefault();
      if (Q.idx < Q.data.questions.length - 1) { Q.idx += 1; rerender(); } else if (Q.data.questions.every((_, i) => Number.isInteger(Q.answers[i]))) submitTest(state.course);
    }
  });
}

export function viewTest() {
  const c = state.course;
  const Q = state.quiz;
  bindTestKeys();
  if (Q.locked) return lockScreen(c, Q.part);
  if (Q.error) {
    return h("div", { class: "test-wrap" }, h("div", { class: "notice" }, Q.error),
      h("p", { style: { marginTop: "16px" } }, h("a", { href: `#/learn/${c.skill}` }, `← ${t("back_course")}`)));
  }
  if (Q.result) return testResult(c);
  const isFinal = Q.part === "final";
  const total = Q.data.questions.length;
  const i = Q.idx;
  const q = Q.data.questions[i];
  const answered = (k) => Number.isInteger(Q.answers[k]);
  const all = Q.data.questions.every((_, k) => answered(k));
  return h("div", { class: "test-wrap" },
    h("div", { class: "test-top" },
      h("a", { class: "pt-back", href: `#/learn/${c.skill}` }, icon("arrowLeft"), h("span", {}, c.title)),
      h("span", { class: "small muted" }, t("test_rule", { n: total, p: Q.data.pass_mark }))),
    h("div", { class: "test-head" },
      h("span", { class: `test-kind ${isFinal ? "final" : ""}` }, icon(isFinal ? "award" : "check"), isFinal ? t("final_test") : t("chapter_test", { n: Q.part })),
      h("h1", {}, isFinal ? c.title : Q.data.chapter_title)),
    h("div", { class: `test-dots ${total > 12 ? "many" : ""}` }, Q.data.questions.map((_, k) => h("button", {
      type: "button", class: `${k === i ? "current" : ""} ${answered(k) ? "answered" : ""}`, "aria-label": t("question_x", { n: k + 1, total }),
      "aria-current": k === i ? "step" : null, onclick: () => { Q.idx = k; rerender(); } }))),
    h("div", { class: "test-card-q" },
      h("span", { class: "eyebrow" }, t("question_x", { n: i + 1, total })),
      h("h2", { id: "q-text" }, q.q),
      h("div", { class: "options", role: "radiogroup", "aria-labelledby": "q-text" }, q.options.map((opt, oi) => h("button", {
        type: "button", role: "radio", "aria-checked": String(Q.answers[i] === oi), class: `option ${Q.answers[i] === oi ? "selected" : ""}`,
        onclick: () => { Q.answers[i] = oi; rerender(); } },
      h("span", { class: "letter" }, LETTERS[oi]), h("span", {}, opt)))),
      h("p", { class: "tiny muted test-from" }, t("from_lesson", { title: q.lesson_title }))),
    h("div", { class: "test-nav" },
      h("button", { type: "button", class: "btn btn-secondary", disabled: i === 0, onclick: () => { Q.idx -= 1; rerender(); } }, "← ", t("back")),
      h("span", { class: "tiny muted hide-sm" }, t("keyboard_hint", { n: q.options.length })),
      i < total - 1
        ? h("button", { type: "button", class: "btn btn-primary", disabled: !answered(i), onclick: () => { Q.idx += 1; rerender(); } }, t("next_q"), " →")
        : h("button", { type: "button", class: "btn btn-primary", disabled: !all || Q.busy, onclick: () => submitTest(c) },
          all ? t("submit") : t("unanswered", { n: Q.data.questions.filter((_, k) => !answered(k)).length }))));
}

// ---------------------------------------------------------------- certificate (always English, like most professional credentials)
// The certificate is one SVG drawn on a fixed A4-landscape grid (1123 × 794 = 297 × 210 mm at 96 dpi). It scales as a
// whole — on any screen and on any paper — so printing or "Save as PDF" can never reflow or push text around, and the
// text stays vector in the PDF.
const CERT_W = 1123;
const CERT_H = 794;
const CERT_FONT = "Roboto, 'Helvetica Neue', Arial, 'PingFang SC', 'Microsoft YaHei', sans-serif";

function svgText(x, y, size, text, attrs = {}) {
  return s("text", { x, y, "font-size": size, ...attrs }, text);
}

// Shrinks a single-line text until it fits maxWidth (needs the SVG in the document so lengths can be measured).
function fitWidth(el, maxWidth, minSize) {
  let size = Number(el.getAttribute("font-size"));
  while (el.getComputedTextLength() > maxWidth && size > minSize) {
    size -= 1;
    el.setAttribute("font-size", size);
  }
  return el.getComputedTextLength() <= maxWidth;
}

// Greedy word wrap into at most maxLines <tspan> lines of maxWidth.
function wrapText(el, text, maxWidth, lineHeight, maxLines) {
  const x = el.getAttribute("x");
  el.textContent = "";
  let line = s("tspan", { x, dy: 0 });
  el.append(line);
  let lines = 1;
  for (const word of text.split(/\s+/)) {
    const before = line.textContent;
    line.textContent = before ? `${before} ${word}` : word;
    if (before && line.getComputedTextLength() > maxWidth && lines < maxLines) {
      line.textContent = before;
      line = s("tspan", { x, dy: lineHeight }, word);
      el.append(line);
      lines += 1;
    }
  }
}

// The person's name: one large line if it fits, otherwise two balanced lines.
function layoutName(el, name) {
  el.textContent = name;
  el.setAttribute("font-size", 60);
  if (fitWidth(el, 900, 44)) return;
  const words = name.split(/\s+/);
  let best = null;
  for (let i = 1; i < words.length; i++) {
    const a = words.slice(0, i).join(" ");
    const b = words.slice(i).join(" ");
    const score = Math.abs(a.length - b.length);
    if (!best || score < best.score) best = { a, b, score };
  }
  if (!best) { fitWidth(el, 900, 18); return; } // one very long word
  const x = el.getAttribute("x");
  el.textContent = "";
  el.setAttribute("font-size", 42);
  el.setAttribute("y", Number(el.getAttribute("y")) - 30);
  el.append(s("tspan", { x, dy: 0 }, best.a), s("tspan", { x, dy: 48 }, best.b));
  while ([...el.children].some((t) => t.getComputedTextLength() > 900) && Number(el.getAttribute("font-size")) > 24) {
    el.setAttribute("font-size", Number(el.getAttribute("font-size")) - 1);
  }
}

// The Path.AI logo (mark + wordmark) as vector paths, so it stays sharp in a printed or saved PDF.
function brandLockup(x, y, markH) {
  const m = BRAND.mark;
  const w = BRAND.word;
  const ms = markH / m.h;
  const wordH = markH * 0.58;
  const ws = wordH / w.h;
  const wordX = x + m.w * ms + markH * 0.2;
  return {
    width: wordX - x + w.w * ws,
    node: s("g", { "aria-label": "Path.AI" },
      s("defs", {}, s("linearGradient", { id: "cert-brand", x1: 0, y1: 1, x2: 1, y2: 0 }, m.stops.map(([o, col]) => s("stop", { offset: o, "stop-color": col })))),
      s("path", { d: m.d, fill: "url(#cert-brand)", "fill-rule": "evenodd", transform: `translate(${x} ${y}) scale(${ms})` }),
      s("g", { transform: `translate(${wordX} ${y + (markH - wordH) / 2 + markH * 0.04}) scale(${ws})` },
        s("path", { d: w.navy, fill: w.navyColor, "fill-rule": "evenodd" }), s("path", { d: w.blue, fill: w.blueColor, "fill-rule": "evenodd" }))),
  };
}

function certificateSvg(c, verify, note) {
  const brand = brandLockup(92, 84, 48);
  const ribbon = icon("award");
  for (const [k, v] of Object.entries({ x: 949, y: 34, width: 52, height: 52, color: "#fedb00" })) ribbon.setAttribute(k, v);
  const goals = c.sdgs.map((g) => goalOf(g)).filter(Boolean);
  const label = (x, text) => svgText(x, 638, 12.5, text.toUpperCase(), { fill: "#6b6b6b", "letter-spacing": 1.4 });
  const value = (x, text, attrs = {}) => svgText(x, 666, 17, text, { fill: "#1e1e1e", "font-weight": 500, ...attrs });
  return s("svg", { class: "cert-svg", viewBox: `0 0 ${CERT_W} ${CERT_H}`, preserveAspectRatio: "xMidYMid meet", role: "img",
    "aria-label": `Path.AI certificate of completion: ${c.name}, ${c.course}`, "font-family": CERT_FONT, "text-rendering": "geometricPrecision" },
  s("defs", {}, s("linearGradient", { id: "cert-ribbon", x1: 0, y1: 0, x2: 0, y2: 1 },
    s("stop", { offset: 0, "stop-color": "#324dc7" }), s("stop", { offset: 1, "stop-color": "#192764" }))),
  s("rect", { x: 0, y: 0, width: CERT_W, height: CERT_H, fill: "#192764" }),
  s("rect", { x: 14, y: 14, width: CERT_W - 28, height: CERT_H - 28, fill: "#ffffff" }),
  s("rect", { x: 30, y: 30, width: CERT_W - 60, height: CERT_H - 60, fill: "none", stroke: "#c9a227", "stroke-width": 1.2 }),
  s("polygon", { points: "925,14 1025,14 1025,150 975,122 925,150", fill: "url(#cert-ribbon)" }),
  ribbon,
  brand.node,
  svgText(92 + brand.width + 22, 117, 13.5, `Certificate ID ${c.id}`, { fill: "#6b6b6b", "letter-spacing": 0.8 }),
  svgText(92, 252, 16, "CERTIFICATE OF COMPLETION", { fill: "#324dc7", "font-weight": 700, "letter-spacing": 5 }),
  svgText(92, 292, 20, "This certifies that", { fill: "#505050" }),
  svgText(92, 380, 60, c.name, { class: "cert-name", fill: "#1e1e1e", "font-weight": 300, "letter-spacing": -0.6 }),
  svgText(92, 446, 20, "has successfully completed the course", { fill: "#505050" }),
  svgText(92, 494, 34, c.course, { class: "cert-course", fill: "#192764", "font-weight": 500 }),
  svgText(92, 532, 17, `${c.lessons} lessons · about ${c.hours} hours of study · final assessment passed with ${c.score}/${c.total}`,
    { class: "cert-detail", fill: "#505050" }),
  s("line", { x1: 92, y1: 604, x2: CERT_W - 92, y2: 604, stroke: "#e8e8e8", "stroke-width": 1.5 }),
  label(92, "Date issued"), value(92, dateLabel(c.date, "en")),
  label(262, "Issued by"), value(262, "Path.AI"),
  label(402, "Verify at"), value(402, verify, { class: "cert-verify", "font-size": 15.5 }),
  goals.length ? [label(812, "Supports UN goals"), goals.map((g, i) => s("g", { transform: `translate(${812 + i * 38} 648)` },
    s("rect", { width: 30, height: 30, rx: 6, fill: g.color }),
    svgText(15, 20.5, 14, String(g.goal), { fill: "#ffffff", "font-weight": 700, "text-anchor": "middle" })))] : null,
  svgText(92, 716, 12.5, note, { class: "cert-note", fill: "#6b6b6b" }));
}

function layoutCertificate(svg) {
  layoutName(svg.querySelector(".cert-name"), svg.querySelector(".cert-name").textContent);
  fitWidth(svg.querySelector(".cert-course"), 900, 22);
  fitWidth(svg.querySelector(".cert-detail"), 940, 13);
  fitWidth(svg.querySelector(".cert-verify"), 390, 11);
  const note = svg.querySelector(".cert-note");
  wrapText(note, note.textContent, 940, 18, 3);
}

export function viewCertificate(token) {
  const v = state.certView;
  if (!v?.valid) {
    return h("div", { class: "container" }, h("div", { class: "notice", style: { marginTop: "32px" } }, t("cert_invalid")));
  }
  const c = v.certificate;
  const url = `${location.origin}/#/certificate/${token}`;
  const copy = async () => {
    try { await navigator.clipboard.writeText(url); toast(t("link_copied")); } catch { toast(url); }
  };
  const providers = c.providers.length > 2 ? `${c.providers.slice(0, 2).join(", ")} and ${c.providers.length - 2} more` : c.providers.join(" and ");
  const note = `Course content from ${providers}, used under open licences. This certificate confirms completion of a free Path.AI course and its assessment; it is not an accredited qualification.`;
  const svg = certificateSvg(c, `${location.host}/#/certificate/…${token.slice(-8)}`, note);
  // measure once the SVG is in the page and the web font has loaded (text widths depend on it)
  requestAnimationFrame(() => (document.fonts?.ready || Promise.resolve()).then(() => { if (svg.isConnected) layoutCertificate(svg); }));
  return h("div", { class: "container" },
    h("div", { class: "cert-bar no-print" },
      h("span", { class: "badge robust" }, `✓ ${t("cert_valid")}`),
      h("span", { class: "spacer" }),
      h("button", { type: "button", class: "btn btn-primary btn-sm", onclick: () => window.print() }, t("download_pdf")),
      h("button", { type: "button", class: "btn btn-secondary btn-sm", onclick: copy }, t("copy_link")),
      h("a", { class: "btn btn-link", href: "#/learn" }, t("back_learn"))),
    h("section", { class: "cert-sheet", "aria-label": "Certificate" }, svg),
    h("p", { class: "tiny muted no-print", style: { textAlign: "center", marginTop: "12px" } }, t("cert_print_tip")),
    // only for the holder (the certificate is in this browser), not for someone checking a shared link
    state.certs[c.skill]?.token === token ? h("p", { class: "no-print", style: { textAlign: "center", marginTop: "20px" } },
      h("a", { class: "btn btn-primary", href: "#/next?mode=work" }, icon("briefcase"), t("nx_cert_cta", { skill: skillName(c.skill) }))) : null);
}

export function certificatePrintStyle(on) {
  let el = document.getElementById("print-page");
  if (on && !el) {
    el = h("style", { id: "print-page" }, `
      @page { size: A4 landscape; margin: 0; }
      @media print {
        html, body { background: #fff !important; margin: 0 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        .site-header, .site-footer, .no-print, .toast, .tooltip { display: none !important; }
        #main, #main > .container { max-width: none !important; margin: 0 !important; padding: 0 !important; }
        .cert-sheet { max-width: none !important; width: 100% !important; margin: 0 !important; box-shadow: none !important; }
        /* fills the page; if a browser ignores the A4-landscape page size it still scales the whole sheet to fit */
        .cert-svg { width: 100% !important; height: auto !important; max-height: calc(100vh - 2mm) !important; }
      }`);
    document.head.append(el);
  } else if (!on && el) {
    el.remove();
  }
}
