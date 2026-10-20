// Learn tab: course catalog, lessons, final quiz and Path.AI certificates.
import { h, trendSpan } from "./charts.js";
import { state, store, t, api, loc, skillName, roleTitle, hasProfile, sdgBadge, costTag, icon, rerender, go, toast,
  ensureRadar, ensureMatches, ensureCourses, dateLabel } from "./core.js";

const CATS = ["all", "ai_data", "digital", "green", "human"];

function progressOf(sid) {
  return state.learned[sid] || { done: [] };
}

function markLesson(sid, lessonId) {
  const p = progressOf(sid);
  if (!p.done.includes(lessonId)) {
    state.learned[sid] = { ...p, done: [...p.done, lessonId] };
    store.set("learned", state.learned);
  }
}

export function courseMinutes(sid) {
  return state.courses?.find((c) => c.skill === sid)?.minutes;
}

// ---------------------------------------------------------------- data
export async function ensureLearn(route) {
  await ensureCourses();
  if (route.name === "learn") {
    await ensureRadar();
    if (route.arg) {
      if (state.course?.skill !== route.arg) {
        state.course = await api(`/api/learn/course/${encodeURIComponent(route.arg)}`);
        const done = progressOf(route.arg).done.length;
        state.step = state.certs[route.arg] ? 3 : Math.min(done, state.course.lessons.length);
        state.quiz = { answers: [], result: null, name: state.quiz.name, busy: false };
      }
      const step = route.params.get("step");
      if (step === "quiz") state.step = state.course.lessons.length;
    } else if (hasProfile()) {
      await ensureMatches();
    }
  }
  if (route.name === "certificate" && state.certViewToken !== route.arg) {
    state.certView = await api(`/api/certificates/verify/${encodeURIComponent(route.arg || "")}`);
    state.certViewToken = route.arg;
  }
}

// ---------------------------------------------------------------- catalog
function courseCard(c, trend) {
  const cert = state.certs[c.skill];
  const done = progressOf(c.skill).done.length;
  const status = cert ? h("span", { class: "badge robust" }, `✓ ${t("certified")}`)
    : done ? h("span", { class: "badge" }, t("progress_n", { done, n: c.lessons })) : null;
  return h("a", { class: "course-card", href: `#/learn/${c.skill}`, style: { "--fam": `var(--fam-${c.category})` } },
    h("span", { class: "tiny muted cat" }, loc(state.meta.categories[c.category])),
    h("h3", {}, skillName(c.skill)),
    h("p", { class: "small" }, c.summary),
    h("span", { class: "course-meta" }, h("span", {}, `${t("lessons_n", { n: c.lessons })} · ${t("minutes_n", { n: c.minutes })}`),
      trend ? trendSpan(trend.pct, ` ${t("per_year")}`) : null),
    status);
}

function recommendation() {
  if (!hasProfile() || !state.matches?.roles?.length) return null;
  const top = state.matches.roles[0];
  const ids = top.items.filter((i) => i.status !== "have").sort((a, b) => b.weight - a.weight).map((i) => i.id);
  const picks = ids.map((id) => state.courses.find((c) => c.skill === id)).filter(Boolean).slice(0, 3);
  return picks.length ? { role: top.id, picks } : null;
}

export function viewLearn() {
  const trend = Object.fromEntries((state.radar?.skills || []).map((s) => [s.id, s]));
  const f = state.learnFilter;
  const q = f.q.trim().toLowerCase();
  const visible = state.courses.filter((c) => (f.cat === "all" || c.category === f.cat)
    && (!q || skillName(c.skill).toLowerCase().includes(q) || c.summary.toLowerCase().includes(q)));
  const rec = recommendation();
  const certs = Object.entries(state.certs);
  const grid = h("div", { class: "course-grid" }, visible.map((c) => courseCard(c, trend[c.skill])));
  const search = h("input", { type: "search", placeholder: t("search_courses"), "aria-label": t("search_courses"), value: f.q,
    oninput: (e) => {
      f.q = e.target.value;
      const qq = f.q.trim().toLowerCase();
      grid.replaceChildren(...state.courses.filter((c) => (f.cat === "all" || c.category === f.cat)
        && (!qq || skillName(c.skill).toLowerCase().includes(qq) || c.summary.toLowerCase().includes(qq))).map((c) => courseCard(c, trend[c.skill])));
    } });
  return h("div", {},
    h("section", { class: "page-head" }, h("div", { class: "container" },
      h("h1", {}, t("learn_title")), h("p", {}, t("learn_sub")),
      h("p", { class: "small muted", style: { marginTop: "6px" } }, t("learn_stats", { n: state.courses.length })))),
    h("section", { class: "band", style: { paddingTop: "28px" } }, h("div", { class: "container stack" },
      certs.length ? h("div", { class: "card" }, h("h3", { style: { marginBottom: "12px" } }, t("my_certs")),
        h("div", { class: "row", style: { gap: "10px" } }, certs.map(([sid, c]) => h("a", { class: "cert-chip", href: `#/certificate/${c.token}` },
          icon("award"), h("span", {}, skillName(sid)), h("span", { class: "tiny muted" }, dateLabel(c.date)))))) : null,
      rec ? h("div", {}, h("h2", { style: { marginBottom: "14px" } }, t("recommended", { role: roleTitle(rec.role) })),
        h("div", { class: "course-grid" }, rec.picks.map((c) => courseCard(c, trend[c.skill])))) : null,
      h("div", {},
        h("h2", { style: { marginBottom: "14px" } }, t("all_courses")),
        h("div", { class: "row", style: { gap: "12px", marginBottom: "18px" } },
          h("div", { class: "chips" }, CATS.map((cat) => h("button", { type: "button", class: `chip ${f.cat === cat ? "on" : ""}`, "aria-pressed": String(f.cat === cat),
            onclick: () => { f.cat = cat; rerender(); } }, cat === "all" ? t("cat_all") : loc(state.meta.categories[cat])))),
          h("span", { class: "spacer" }),
          h("div", { class: "search compact" }, icon("search"), search)),
        grid),
      h("p", { class: "source-line" }, t("learn_license")))));
}

// ---------------------------------------------------------------- course
function reading(r) {
  const blocks = r.blocks.map((b) => (typeof b === "string" ? h("p", {}, b) : h("ul", {}, b.list.map((x) => h("li", {}, x)))));
  return h("div", { class: "reading" },
    h("div", { class: "reading-label" }, icon("book"), t("reading")),
    blocks,
    h("p", { class: "attribution" }, `${t("excerpt_from")} “`, h("a", { href: r.permalink, target: "_blank", rel: "noopener" }, r.title),
      `” ${t("on_wikipedia")} · `, h("a", { href: r.license_url, target: "_blank", rel: "noopener" }, r.license),
      r.shortened ? ` · ${t("shortened")}` : "", " · ", h("a", { href: r.url, target: "_blank", rel: "noopener" }, `${t("read_full")} ↗`)));
}

function lessonCard(c, i) {
  const l = c.lessons[i];
  const last = i === c.lessons.length - 1;
  const next = () => { markLesson(c.skill, l.id); state.step = i + 1; rerender(); window.scrollTo({ top: 0 }); };
  return h("article", { class: "card lesson" },
    h("div", { class: "tiny muted" }, t("lesson_of", { n: i + 1, total: c.lessons.length }).toUpperCase()),
    h("h2", {}, l.title),
    h("div", { class: "callout why" }, h("b", {}, t("why_matters")), h("p", {}, l.why)),
    reading(l.reading),
    h("div", { class: "callout try" }, h("b", {}, t("try_it")), h("p", {}, l.try)),
    h("div", { class: "lesson-nav" },
      i > 0 ? h("button", { type: "button", class: "btn btn-link", onclick: () => { state.step = i - 1; rerender(); } }, `← ${t("prev")}`) : h("span"),
      h("button", { type: "button", class: "btn btn-primary", onclick: next }, last ? `${t("take_quiz")} →` : `${t("next_lesson")} →`)));
}

async function submitQuiz(c) {
  state.quiz.busy = true;
  rerender();
  try {
    state.quiz.result = await api(`/api/learn/course/${c.skill}/grade`, { answers: state.quiz.answers });
    if (state.quiz.result.passed) {
      state.learned[c.skill] = { ...progressOf(c.skill), passed: true };
      store.set("learned", state.learned);
    }
  } catch (e) { toast(String(e.message || e)); }
  state.quiz.busy = false;
  rerender();
}

async function createCertificate(c) {
  state.quiz.busy = true;
  rerender();
  try {
    const { certificate } = await api(`/api/learn/course/${c.skill}/certificate`, { answers: state.quiz.answers, name: state.quiz.name });
    state.certs[c.skill] = { token: certificate.token, id: certificate.id, date: certificate.date, score: certificate.score, total: certificate.total };
    store.set("certs", state.certs);
    store.set("certName", state.quiz.name);
    state.quiz.busy = false;
    go(`#/certificate/${certificate.token}`);
    return;
  } catch (e) { toast(String(e.message || e)); }
  state.quiz.busy = false;
  rerender();
}

function quizCard(c) {
  const qz = state.quiz;
  const res = qz.result;
  const cert = state.certs[c.skill];
  const questions = c.quiz.map((q, qi) => {
    const r = res?.results[qi];
    return h("fieldset", { class: `q ${r ? (r.correct ? "ok" : "bad") : ""}` },
      h("legend", {}, `${qi + 1}. ${q.q}`),
      q.options.map((opt, oi) => h("label", { class: `opt ${res?.passed && r.answer === oi ? "key" : ""}` },
        h("input", { type: "radio", name: `q${qi}`, value: String(oi), checked: qz.answers[qi] === oi, disabled: !!res,
          onchange: () => { qz.answers[qi] = oi; rerender(); } }),
        h("span", {}, opt))),
      r ? h("p", { class: "q-feedback" }, r.correct ? "✓ " : "✗ ",
        res.passed ? r.explain : h("button", { type: "button", class: "btn btn-link", onclick: () => { state.step = r.lesson - 1; rerender(); window.scrollTo({ top: 0 }); } },
          t("review_lesson", { n: r.lesson }))) : null);
  });
  const answered = c.quiz.every((_, i) => Number.isInteger(qz.answers[i]));
  let footer;
  if (!res) {
    footer = h("div", { class: "lesson-nav" }, h("span", { class: "small muted" }, t("quiz_sub", { n: c.quiz.length, p: c.pass_mark })),
      h("button", { type: "button", class: "btn btn-primary", disabled: !answered || qz.busy, onclick: () => submitQuiz(c) }, t("submit_answers")));
  } else if (!res.passed) {
    footer = h("div", {},
      h("div", { class: "lesson-nav" }, h("span"), h("button", { type: "button", class: "btn btn-primary",
        onclick: () => { state.quiz = { answers: [], result: null, name: qz.name, busy: false }; rerender(); } }, t("try_again"))));
  } else {
    if (!qz.name) qz.name = store.get("certName", "");
    footer = h("div", { class: "stack" },
      h("label", { class: "field-label" }, t("cert_name"),
        h("input", { type: "text", class: "text-input", maxlength: 60, autocomplete: "name", value: qz.name, oninput: (e) => { qz.name = e.target.value; } })),
      h("div", { class: "lesson-nav" }, h("span", { class: "tiny muted" }, t("cert_privacy")),
        h("button", { type: "button", class: "btn btn-primary", disabled: qz.busy, onclick: () => createCertificate(c) }, icon("award"), qz.busy ? t("cert_creating") : t("get_cert"))));
  }
  return h("article", { class: "card lesson" },
    h("div", { class: "tiny muted" }, t("quiz_title").toUpperCase()),
    h("h2", {}, t("quiz_heading", { course: skillName(c.skill) })),
    cert && !res ? h("div", { class: "notice good", style: { margin: "12px 0" } }, `✓ ${t("already_certified")} `,
      h("a", { href: `#/certificate/${cert.token}` }, t("view_cert"))) : null,
    res ? h("div", { class: `notice ${res.passed ? "good" : ""}`, style: { margin: "12px 0 16px" } },
      res.passed ? t("passed_t", { s: res.score, n: res.total }) : t("failed_t", { s: res.score, n: res.total, p: res.pass_mark })) : null,
    h("form", { class: "quiz", onsubmit: (e) => e.preventDefault() }, questions),
    footer);
}

export function viewCourse() {
  const c = state.course;
  const done = progressOf(c.skill).done;
  const cert = state.certs[c.skill];
  const trend = state.radar?.skills.find((s) => s.id === c.skill);
  const steps = h("ol", { class: "course-steps" },
    c.lessons.map((l, i) => h("li", {}, h("button", { type: "button", class: `cs ${i === state.step ? "on" : ""} ${done.includes(l.id) ? "done" : ""}`,
      "aria-current": i === state.step ? "step" : null, onclick: () => { state.step = i; rerender(); } },
    h("span", { class: "n" }, done.includes(l.id) ? "✓" : String(i + 1)), h("span", { class: "t" }, l.title)))),
    h("li", {}, h("button", { type: "button", class: `cs ${state.step === c.lessons.length ? "on" : ""} ${cert ? "done" : ""}`,
      onclick: () => { state.step = c.lessons.length; rerender(); } },
    h("span", { class: "n" }, cert ? "✓" : "?"), h("span", { class: "t" }, t("quiz_title")))));
  const main = state.step < c.lessons.length ? lessonCard(c, state.step) : quizCard(c);
  const side = [
    h("div", { class: "card" }, h("h3", { style: { marginBottom: "10px" } }, t("your_progress")),
      h("div", { class: "progress", style: { marginTop: "0" } }, h("span", { style: { width: `${(Math.min(done.length, c.lessons.length) / c.lessons.length) * 100}%` } })),
      h("p", { class: "small muted", style: { marginTop: "8px" } }, cert ? `✓ ${t("certified")} · ${dateLabel(cert.date)}` : t("progress_n", { done: done.length, n: c.lessons.length })),
      cert ? h("a", { class: "btn btn-secondary btn-sm", href: `#/certificate/${cert.token}`, style: { marginTop: "10px" } }, icon("award"), t("view_cert")) : null),
    c.practice ? h("div", { class: "card" }, h("h3", {}, t("practice_t")), h("p", { class: "small", style: { marginTop: "6px" } }, c.practice)) : null,
    c.resources.length ? h("div", { class: "card" }, h("h3", { style: { marginBottom: "8px" } }, t("deeper_t")),
      h("ul", { class: "plain-list" }, c.resources.map((r) => h("li", {}, h("a", { href: r.url, target: "_blank", rel: "noopener" }, r.title), h("br"),
        h("span", { class: "tiny muted" }, `${r.provider} · ~${r.hours} h `), costTag(r.cost))))) : null,
    c.sdgs.length ? h("div", { class: "card" }, h("h3", { style: { marginBottom: "10px" } }, t("sdg_t")),
      c.sdgs.map((s) => h("div", { class: "row", style: { gap: "10px", flexWrap: "nowrap", alignItems: "flex-start", marginTop: "6px" } },
        sdgBadge(s.goal, true), h("span", { class: "small" }, h("b", {}, `${s.target} `), s.why)))) : null,
  ];
  return h("div", {},
    h("section", { class: "page-head" }, h("div", { class: "container" },
      h("p", { style: { marginBottom: "10px" } }, h("a", { href: "#/learn" }, `← ${t("all_courses")}`)),
      h("h1", {}, skillName(c.skill)),
      h("p", {}, c.summary),
      h("div", { class: "row", style: { gap: "16px", marginTop: "12px" } },
        h("span", { class: "small muted" }, t("course_meta", { n: c.lessons.length, m: c.minutes })),
        trend ? trendSpan(trend.pct, ` ${t("per_year")}`) : null))),
    h("section", { class: "band", style: { paddingTop: "24px" } }, h("div", { class: "container grid-main" },
      h("div", {}, steps, main),
      h("div", { class: "stack" }, side))));
}

// ---------------------------------------------------------------- certificate (always English, like most professional credentials)
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
  return h("div", { class: "container" },
    h("div", { class: "cert-bar no-print" },
      h("span", { class: "badge robust" }, `✓ ${t("cert_valid")}`),
      h("span", { class: "spacer" }),
      h("button", { type: "button", class: "btn btn-primary btn-sm", onclick: () => window.print() }, t("download_pdf")),
      h("button", { type: "button", class: "btn btn-secondary btn-sm", onclick: copy }, t("copy_link")),
      h("a", { class: "btn btn-link", href: "#/learn" }, t("back_learn"))),
    h("section", { class: "certificate", "aria-label": "Certificate" },
      h("div", { class: "cert-top" }, h("span", { class: "cert-logo" }, "Path", h("span", { class: "dot" }, "."), "AI"),
        h("span", { class: "cert-id" }, `Certificate ID ${c.id}`)),
      h("p", { class: "cert-kicker" }, "Certificate of Completion"),
      h("p", { class: "cert-line" }, "This certifies that"),
      h("p", { class: "cert-name" }, c.name),
      h("p", { class: "cert-line" }, "has completed the Path.AI micro-course"),
      h("p", { class: "cert-course" }, c.course),
      h("p", { class: "cert-line" }, `and passed the final assessment with a score of ${c.score}/${c.total}.`),
      h("div", { class: "cert-foot" },
        h("div", {}, h("span", { class: "k" }, "Date issued"), h("span", { class: "v" }, dateLabel(c.date, "en"))),
        h("div", {}, h("span", { class: "k" }, "Verify at"), h("span", { class: "v small" }, `${location.host}/#/certificate/…${token.slice(-8)}`)),
        c.sdgs.length ? h("div", {}, h("span", { class: "k" }, "Supports UN goals"), h("span", { class: "row", style: { gap: "4px" } }, c.sdgs.map((g) => sdgBadge(g, true)))) : null),
      h("p", { class: "cert-note" }, "Course readings include excerpts from Wikipedia (CC BY-SA 4.0). This certificate confirms completion of a free Path.AI micro-course and its assessment; it is not an accredited qualification.")));
}

export function certificatePrintStyle(on) {
  let el = document.getElementById("print-page");
  if (on && !el) {
    el = h("style", { id: "print-page" }, "@page { size: A4 landscape; margin: 10mm; }");
    document.head.append(el);
  } else if (!on && el) {
    el.remove();
  }
}
