// Learn tab: full open courses — catalog, course overview, lesson player, final test and Path.AI certificates.
import { h, trendSpan } from "./charts.js";
import { state, store, t, api, loc, skillName, roleTitle, hasProfile, sdgBadge, icon, rerender, go, toast,
  ensureRadar, ensureMatches, ensureCourses, dateLabel } from "./core.js";

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
  healthcare_basics: "heart", lifelong_learning: "bookOpen", finance_domain: "trend",
};
const courseIcon = (c) => icon(SKILL_ICON[c.skill] || CAT_ICON[c.category] || "book");
const LETTERS = "ABCDE";

// ---------------------------------------------------------------- progress (kept in this browser only)
const progressOf = (sid) => state.learned[sid] || { done: [] };

function saveProgress(sid, patch) {
  state.learned[sid] = { ...progressOf(sid), ...patch, at: Date.now() };
  store.set("learned", state.learned);
}

function markDone(sid, lid) {
  const p = progressOf(sid);
  if (!p.done.includes(lid)) saveProgress(sid, { done: [...p.done, lid] });
}

const pctDone = (sid, total) => (total ? Math.round((Math.min(progressOf(sid).done.length, total) / total) * 100) : 0);

export function hoursLabel(minutes) {
  if (minutes < 60) return t("minutes_n", { n: minutes });
  return t("hours_n", { h: String(Math.round(minutes / 6) / 10) });
}

// used by the plan view
export function courseLength(sid) {
  const c = state.courses?.find((x) => x.skill === sid);
  return c ? hoursLabel(c.minutes) : null;
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
  if (route.sub === "test") {
    if (state.quiz.sid !== sid) {
      const data = await api(`/api/learn/course/${encodeURIComponent(sid)}/quiz`);
      state.quiz = { sid, data, answers: [], idx: 0, result: null, name: store.get("certName", ""), busy: false };
    }
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
    h("span", { class: "rt" }, h("b", {}, c.title), h("span", { class: "small muted" }, t("lessons_done", { done: p.done.length, n: c.lessons }))),
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
    h("section", { class: "learn-hero" }, h("div", { class: "container" },
      h("span", { class: "eyebrow" }, t("learn_eyebrow")),
      h("h1", {}, t("learn_title")),
      h("p", { class: "lead" }, t("learn_sub")),
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

function nextLesson(c) {
  const done = new Set(progressOf(c.skill).done);
  for (const m of c.syllabus) for (const l of m.lessons) if (!done.has(l.id)) return l;
  return null;
}

function lessonNumber(c, lid) {
  return c.syllabus.flatMap((m) => m.lessons).findIndex((l) => l.id === lid) + 1;
}

function primaryAction(c, cls = "btn btn-primary btn-lg") {
  const cert = state.certs[c.skill];
  const p = progressOf(c.skill);
  const next = nextLesson(c);
  if (cert) return h("a", { class: cls, href: `#/certificate/${cert.token}` }, icon("award"), t("view_cert"));
  if (!next) return h("a", { class: cls, href: `#/learn/${c.skill}/test` }, t("take_test"), " →");
  if (!p.done.length) return h("a", { class: cls, href: `#/learn/${c.skill}/${next.id}` }, t("start_course"), " →");
  return h("a", { class: cls, href: `#/learn/${c.skill}/${next.id}` }, t("resume_course", { n: lessonNumber(c, next.id) }), " →");
}

function moduleBlock(c, m, i, done, openIndex) {
  const doneHere = m.lessons.filter((l) => done.has(l.id)).length;
  const complete = doneHere === m.lessons.length;
  return h("details", { class: "module", open: i === openIndex },
    h("summary", {},
      h("span", { class: `mod-n ${complete ? "done" : ""}` }, complete ? icon("check") : String(i + 1)),
      h("span", { class: "mod-t" }, h("b", {}, m.title),
        h("span", { class: "small muted" }, `${t("lessons_n", { n: m.lessons.length })} · ${hoursLabel(m.minutes)} · ${doneHere}/${m.lessons.length}`)),
      h("span", { class: "mod-chev" }, icon("chevron"))),
    h("ol", { class: "lesson-list" }, m.lessons.map((l) => h("li", {},
      h("a", { href: `#/learn/${c.skill}/${l.id}`, class: done.has(l.id) ? "done" : "" },
        h("span", { class: "st" }, done.has(l.id) ? icon("check") : icon("play")),
        h("span", { class: "lt" }, l.title),
        h("span", { class: "lm" }, t("minutes_n", { n: l.minutes })))))));
}

export function viewCourse() {
  const c = state.course;
  const p = progressOf(c.skill);
  const done = new Set(p.done);
  const cert = state.certs[c.skill];
  const pct = pctDone(c.skill, c.lessons);
  const next = nextLesson(c);
  const openIndex = Math.max(0, c.syllabus.findIndex((m) => m.lessons.some((l) => !done.has(l.id))));
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
          chip("check", t("chip_test", { n: c.questions })),
          chip("award", t("chip_cert"))),
        h("div", { class: "ch-cta" }, primaryAction(c),
          h("a", { class: "btn btn-ghost btn-lg", href: "#syllabus", onclick: (e) => { e.preventDefault(); document.getElementById("syllabus")?.scrollIntoView({ behavior: "smooth" }); } },
            t("view_syllabus"))),
        h("p", { class: "ch-provider" }, t("built_from"), " ", c.sources.map((s) => s.name).join(" · "))),
      h("aside", { class: "ch-card", "aria-label": t("your_progress") },
        h("div", { class: "top" }, h("span", { class: "ring", style: { "--p": pct } }, h("span", {}, `${pct}%`)),
          h("div", {}, h("b", {}, t("your_progress")), h("span", { class: "small muted" }, cert ? `✓ ${t("certified")} · ${dateLabel(cert.date)}`
            : t("lessons_done", { done: Math.min(p.done.length, c.lessons), n: c.lessons })))),
        next && !cert ? h("div", { class: "next" }, h("span", {}, p.done.length ? t("up_next") : t("first_lesson")), next.title) : null,
        primaryAction(c, "btn btn-primary btn-block"),
        trend ? h("p", { class: "tiny muted" }, t("demand_trend"), " ", trendSpan(trend.pct, ` ${t("per_year")}`)) : null))),
    h("div", { class: "container course-body" },
      h("div", { class: "cb-main" },
        h("section", { class: "card" }, h("h2", {}, t("outcomes_t")),
          h("ul", { class: "outcomes" }, c.outcomes.map((o) => h("li", {}, icon("check"), h("span", {}, o))))),
        h("section", { id: "syllabus" },
          h("div", { class: "syl-head" }, h("h2", {}, t("syllabus_t")),
            h("span", { class: "small muted" }, t("syllabus_meta", { m: c.syllabus.length, n: c.lessons, h: hoursLabel(c.minutes) }))),
          c.syllabus.map((m, i) => moduleBlock(c, m, i, done, openIndex))),
        h("section", { class: "card test-card" },
          h("span", { class: "ti" }, icon("award")),
          h("div", {}, h("h3", {}, t("test_card_t")), h("p", { class: "small", style: { marginTop: "4px" } }, t("test_card_d", { n: c.questions, p: c.pass_mark }))),
          cert ? h("a", { class: "btn btn-secondary", href: `#/certificate/${cert.token}` }, t("view_cert"))
            : h("a", { class: "btn btn-primary", href: `#/learn/${c.skill}/test` }, t("take_test")))),
      h("aside", { class: "cb-side" },
        h("section", { class: "card" }, h("h3", {}, t("sources_t")), h("p", { class: "small muted", style: { marginTop: "4px" } }, t("sources_d")),
          h("ul", { class: "src-list" }, c.sources.map((s) => h("li", {},
            h("a", { href: s.url, target: "_blank", rel: "noopener" }, s.name),
            h("span", { class: "tiny muted" }, s.attribution),
            h("a", { class: `lic ${s.noncommercial ? "nc" : ""}`, href: s.license_url, target: "_blank", rel: "noopener" }, s.license))))),
        nc ? h("p", { class: "tiny muted" }, t("nc_note")) : null,
        c.sdgs.length ? h("section", { class: "card" }, h("h3", { style: { marginBottom: "10px" } }, t("sdg_t")),
          c.sdgs.map((s) => h("div", { class: "row", style: { gap: "10px", flexWrap: "nowrap", alignItems: "flex-start", marginTop: "8px" } },
            sdgBadge(s.goal, true), h("span", { class: "small" }, h("b", {}, `${s.target} `), s.why)))) : null,
        c.practice ? h("section", { class: "card" }, h("h3", {}, t("practice_t")), h("p", { class: "small", style: { marginTop: "6px" } }, c.practice)) : null)));
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
  return h("nav", { class: `player-outline ${state.outlineOpen ? "open" : ""}`, "aria-label": t("outline") },
    h("button", { type: "button", class: "btn btn-secondary btn-sm outline-close", onclick: close }, icon("close"), t("close")),
    h("p", { class: "po-title" }, t("outline")),
    c.syllabus.map((m) => h("div", { class: "po-mod" }, h("b", {}, m.title),
      m.lessons.map((l) => h("a", { href: `#/learn/${c.skill}/${l.id}`, class: done.has(l.id) ? "done" : "", "aria-current": l.id === lesson.id ? "page" : null },
        h("span", { class: "dot" }, done.has(l.id) ? icon("check") : null), h("span", {}, l.title))))),
    h("a", { class: "po-test", href: `#/learn/${c.skill}/test` }, icon("award"), t("final_test")));
}

export function viewLesson() {
  const c = state.course;
  const L = state.lesson;
  const done = new Set(progressOf(c.skill).done);
  const pct = pctDone(c.skill, c.lessons);
  const prose = h("div", { class: "lesson-prose" }, safeFragment(L.html));
  prose.addEventListener("click", inPageLinks);
  const toc = L.toc.filter((x) => x.level <= 3);
  const complete = () => {
    markDone(c.skill, L.id);
    go(L.next ? `#/learn/${c.skill}/${L.next}` : `#/learn/${c.skill}/test`);
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
          h("span", { class: "eyebrow" }, `${L.module} · ${t("lesson_x_of_y", { n: L.index, total: L.count })}`),
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
      h("button", { type: "button", class: "btn btn-primary", onclick: complete }, L.next ? t("complete_next") : t("complete_test"), " →"))));
}

// ---------------------------------------------------------------- final test
async function submitTest(c) {
  const Q = state.quiz;
  Q.busy = true;
  rerender();
  try {
    Q.result = await api(`/api/learn/course/${c.skill}/grade`, { answers: Q.data.questions.map((_, i) => (Number.isInteger(Q.answers[i]) ? Q.answers[i] : null)) });
    if (Q.result.passed) saveProgress(c.skill, { passed: true });
    window.scrollTo({ top: 0 });
  } catch (e) { toast(String(e.message || e)); }
  Q.busy = false;
  rerender();
}

async function createCertificate(c) {
  const Q = state.quiz;
  Q.busy = true;
  rerender();
  try {
    const { certificate } = await api(`/api/learn/course/${c.skill}/certificate`, { answers: Q.answers, name: Q.name });
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

function resetTest() {
  const Q = state.quiz;
  state.quiz = { ...Q, answers: [], idx: 0, result: null, busy: false };
  rerender();
  window.scrollTo({ top: 0 });
}

function testResult(c) {
  const Q = state.quiz;
  const r = Q.result;
  const pct = Math.round((r.score / r.total) * 100);
  const head = [
    h("span", { class: "ring lg", style: { "--p": pct } }, h("span", {}, `${r.score}/${r.total}`)),
    h("h2", {}, r.passed ? t("passed_h") : t("failed_h")),
    h("p", {}, r.passed ? t("passed_d", { s: r.score, n: r.total }) : t("failed_d", { s: r.score, n: r.total, p: r.pass_mark })),
  ];
  if (!r.passed) {
    return h("div", { class: "test-wrap" },
      h("div", { class: "result fail" }, head,
        r.review.length ? h("ul", { class: "review-list" }, r.review.map((l) => h("li", {},
          h("a", { href: `#/learn/${c.skill}/${l.id}` }, icon("book"), h("span", {}, l.title))))) : null,
        h("div", { class: "row", style: { justifyContent: "center", marginTop: "8px" } },
          h("button", { type: "button", class: "btn btn-primary", onclick: resetTest }, t("try_again")),
          h("a", { class: "btn btn-secondary", href: `#/learn/${c.skill}` }, t("back_course")))));
  }
  const cert = state.certs[c.skill];
  return h("div", { class: "test-wrap" },
    h("div", { class: "result pass" }, head,
      cert ? h("a", { class: "btn btn-secondary", href: `#/certificate/${cert.token}` }, icon("award"), t("view_cert")) : null,
      h("form", { class: "cert-form", onsubmit: (e) => { e.preventDefault(); createCertificate(c); } },
        h("label", { class: "field-label" }, t("cert_name"),
          h("input", { type: "text", class: "text-input", maxlength: 60, autocomplete: "name", required: true, value: Q.name,
            oninput: (e) => { Q.name = e.target.value; } })),
        h("button", { type: "submit", class: "btn btn-primary btn-block", disabled: Q.busy }, icon("award"), Q.busy ? t("cert_creating") : t("get_cert")),
        h("p", { class: "tiny muted" }, t("cert_privacy")))),
    h("h3", { style: { margin: "28px 0 0" } }, t("review_answers")),
    h("div", { class: "answers" }, Q.data.questions.map((q, i) => {
      const res = r.results[i];
      return h("div", { class: "answer-item" },
        h("p", {}, h("span", { class: res.correct ? "ok" : "" }, res.correct ? "✓ " : "✗ "), h("b", {}, q.q)),
        h("p", { class: "key" }, `${t("correct_answer")}: `, h("b", {}, q.options[res.answer])),
        res.explain ? h("p", { class: "small muted", style: { marginTop: "4px" } }, res.explain) : null,
        res.evidence ? h("blockquote", {}, `“${res.evidence}” — `, h("a", { href: `#/learn/${c.skill}/${q.lesson}` }, q.lesson_title)) : null);
    })));
}

let keysBound = false;
function bindTestKeys() {
  if (keysBound) return;
  keysBound = true;
  document.addEventListener("keydown", (e) => {
    const Q = state.quiz;
    if (!location.hash.endsWith("/test") || !Q?.data || Q.result || e.target.closest("input, textarea") || e.metaKey || e.ctrlKey || e.altKey) return;
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
  if (Q.result) return testResult(c);
  const total = Q.data.questions.length;
  const i = Q.idx;
  const q = Q.data.questions[i];
  const answered = (k) => Number.isInteger(Q.answers[k]);
  const all = Q.data.questions.every((_, k) => answered(k));
  return h("div", { class: "test-wrap" },
    h("div", { class: "test-top" },
      h("a", { class: "pt-back", href: `#/learn/${c.skill}` }, icon("arrowLeft"), h("span", {}, c.title)),
      h("span", { class: "small muted" }, t("test_rule", { n: total, p: Q.data.pass_mark }))),
    h("div", { class: "test-dots" }, Q.data.questions.map((_, k) => h("button", {
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
  return h("div", { class: "container" },
    h("div", { class: "cert-bar no-print" },
      h("span", { class: "badge robust" }, `✓ ${t("cert_valid")}`),
      h("span", { class: "spacer" }),
      h("button", { type: "button", class: "btn btn-primary btn-sm", onclick: () => window.print() }, t("download_pdf")),
      h("button", { type: "button", class: "btn btn-secondary btn-sm", onclick: copy }, t("copy_link")),
      h("a", { class: "btn btn-link", href: "#/learn" }, t("back_learn"))),
    h("section", { class: "certificate", "aria-label": "Certificate" },
      h("span", { class: "cert-ribbon", "aria-hidden": "true" }, icon("award")),
      h("div", { class: "cert-top" }, h("span", { class: "cert-logo" }, "Path", h("span", { class: "dot" }, "."), "AI"),
        h("span", { class: "cert-id" }, `Certificate ID ${c.id}`)),
      h("div", { class: "cert-mid" },
        h("p", { class: "cert-kicker" }, "Certificate of Completion"),
        h("p", { class: "cert-line" }, "This certifies that"),
        h("p", { class: "cert-name" }, c.name),
        h("p", { class: "cert-line" }, "has successfully completed the course"),
        h("p", { class: "cert-course" }, c.course),
        h("p", { class: "cert-detail" }, `${c.lessons} lessons · about ${c.hours} hours of study · final assessment passed with ${c.score}/${c.total}.`)),
      h("div", { class: "cert-foot" },
        h("div", {}, h("span", { class: "k" }, "Date issued"), h("span", { class: "v" }, dateLabel(c.date, "en"))),
        h("div", {}, h("span", { class: "k" }, "Issued by"), h("span", { class: "v" }, "Path.AI")),
        h("div", {}, h("span", { class: "k" }, "Verify at"), h("span", { class: "v small" }, `${location.host}/#/certificate/…${token.slice(-8)}`)),
        c.sdgs.length ? h("div", {}, h("span", { class: "k" }, "Supports UN goals"), h("span", { class: "row", style: { gap: "4px" } }, c.sdgs.map((g) => sdgBadge(g, true)))) : null),
      h("p", { class: "cert-note" }, `Course content from ${providers}, used under open licences. This certificate confirms completion of a free Path.AI course and its assessment; it is not an accredited qualification.`)));
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
