import { h, radar, divergingBars, miniBar, magnitudeBars, sparkline, heatColor, fmtPct, trendSpan } from "./charts.js";
import { state, store, EMPTY_PROFILE, t, setLang, $, api, skillById, roleById, loc, skillName, skillShort, roleTitle, goalOf,
  hasProfile, dateLabel, monthLabel, setRenderer, go, toast, saveProfile, sdgBadge, costTag, icon,
  ensureRadar, ensureMatches, ensureCourses } from "./core.js";
import { ensureLearn, viewLearn, viewCourse, viewCertificate, certificatePrintStyle, courseMinutes } from "./learn.js";

const POPULAR_JOBS = ["accounting_clerk", "admin_assistant", "customer_service_rep", "cashier", "teacher", "graphic_designer"];
const POPULAR_SKILLS = ["prompt_eng", "data_analysis", "communication", "excel", "project_mgmt", "digital_literacy", "leadership", "python", "customer_service", "teaching_training"];

// ---------------------------------------------------------------- profile builders (one tap = a full profile)
function prefillFromRole(rid) {
  const skills = {};
  for (const item of roleById()[rid].skills) skills[item.id] = item.w >= 1 ? 3 : item.w >= 0.5 ? 2 : 1;
  return skills;
}

function freshProfile(skills, currentRole = null) {
  return { ...structuredClone(EMPTY_PROFILE), hours_per_week: state.profile.hours_per_week || 6, skills, current_role: currentRole };
}

function chooseJob(rid) {
  state.profile = freshProfile(prefillFromRole(rid), rid);
  state.origin = { type: "job", id: rid };
  state.wizard = { ...state.wizard, step: 2, student: false, query: "", cvNote: null };
  saveProfile();
  render();
}

function chooseField(field) {
  state.profile = freshProfile({ ...field.skills });
  state.origin = { type: "field", id: field.id };
  state.wizard = { ...state.wizard, step: 2, student: false, cvNote: null };
  saveProfile();
  render();
}

function tilesFromInterests(interests) {
  return state.meta.interest_tiles.filter((tile) => tile.tags.some((tag) => interests.includes(tag))).map((tile) => tile.id);
}

function loadPersona(p) {
  state.profile = { skills: { ...p.skills }, interests: [...p.interests], sdg_priorities: [...p.sdg_priorities], current_role: p.current_role, hours_per_week: p.hours_per_week };
  state.origin = { type: "persona", id: p.id };
  state.tiles = tilesFromInterests(p.interests);
  saveProfile();
}

async function uploadCv(file) {
  if (!file) return;
  state.wizard.busy = true;
  render();
  const form = new FormData();
  form.append("file", file);
  form.append("text", "");
  try {
    const res = await api("/api/profile/parse", form, true);
    const skills = {};
    for (const d of res.skills) skills[d.id] = d.level;
    state.profile = freshProfile(skills);
    state.origin = { type: "cv" };
    state.wizard = { ...state.wizard, step: 2, student: false, cvNote: res };
    saveProfile();
    if (location.hash !== "#/start") location.hash = "#/start";
  } catch (e) { toast(String(e.message || e)); }
  state.wizard.busy = false;
  render();
}

function cvInput(id) {
  return h("input", { type: "file", accept: ".pdf,.txt,.md", class: "sr-only", id, onchange: (e) => uploadCv(e.target.files[0]) });
}

function originLabel() {
  const o = state.origin;
  if (!o) return "–";
  if (o.type === "job") return roleTitle(o.id);
  if (o.type === "field") return loc(state.meta.study_fields.find((f) => f.id === o.id)?.label);
  if (o.type === "cv") return t("your_cv");
  if (o.type === "persona") return t("example_of", { name: state.personas.find((p) => p.id === o.id)?.name || "" });
  return "–";
}

// ---------------------------------------------------------------- header & footer
const NAV = [["results", "nav_path"], ["learn", "nav_learn"], ["trends", "nav_trends"], ["teams", "nav_teams"], ["how", "nav_how"]];

function renderChrome(routeName) {
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : state.lang;
  const nav = $("nav");
  const active = (r) => routeName === r || (r === "results" && (routeName === "plan" || routeName === "start")) || (r === "learn" && routeName === "certificate");
  nav.replaceChildren(...NAV.map(([r, key]) => h("a", { href: `#/${r}`, "aria-current": active(r) ? "page" : null,
    onclick: () => { nav.classList.remove("open"); $("menuBtn").setAttribute("aria-expanded", "false"); } }, t(key))));
  $("cta").textContent = t("cta_start");
  $("cta").setAttribute("href", "#/start?step=1");
  $("cta").style.display = routeName === "start" ? "none" : "";
  $("menuBtn").textContent = t("menu");
  $("menuBtn").onclick = () => { const open = nav.classList.toggle("open"); $("menuBtn").setAttribute("aria-expanded", String(open)); };
  const llm = state.meta.llm || {};
  const langs = [["en", "English"], ["ms", "Bahasa Melayu"], ["zh", "中文"]];
  $("footer").replaceChildren(h("div", { class: "container" },
    h("div", { class: "cols" },
      h("div", {}, h("h4", {}, "Path.AI"), h("p", {}, t("ft_about")),
        h("p", { class: "tiny", style: { marginTop: "10px", color: "#b2b2b2" } }, llm.online ? t("ft_ai_on", { model: llm.model }) : t("ft_ai_off"))),
      h("div", {}, h("h4", {}, t("ft_explore")), NAV.map(([r, key]) => h("a", { href: `#/${r}` }, t(key)))),
      h("div", {}, h("h4", {}, t("ft_lang")), h("div", { class: "lang-switch" }, langs.map(([code, label]) =>
        h("button", { type: "button", "aria-pressed": String(code === state.lang), onclick: () => { setLang(code); render(); } }, label))))),
    h("p", { class: "fine" }, t("ft_fine"))));
}

// ---------------------------------------------------------------- data loaders
async function ensurePathway(rid) {
  const key = JSON.stringify([state.asOf, state.scenario, rid, state.profile]);
  if (state.pathwayKey === key) return;
  state.pathway = await api("/api/pathway", { as_of: state.asOf, scenario: state.scenario, profile: state.profile, role_id: rid });
  state.pathwayKey = key;
}

async function ensureTeam() {
  const key = `${state.asOf}|${state.scenario}`;
  if (state.teamKey === key) return;
  state.team = await api("/api/team", { as_of: state.asOf, scenario: state.scenario });
  state.teamKey = key;
}

// ---------------------------------------------------------------- Home
function trendRows(skills) {
  return h("ul", { class: "trend-list" }, skills.map((x) => h("li", {}, h("span", { class: "name" }, skillShort(x.id)), trendSpan(x.pct, ` ${t("per_year")}`))));
}

function viewHome() {
  const sorted = state.radar.skills.slice().sort((a, b) => b.pct - a.pct);
  const hn = state.meta.signals.hn;
  const examples = state.personas.map((p) => h("button", { class: "example", type: "button", onclick: () => { loadPersona(p); go("#/results"); } },
    h("span", { class: "who" }, `${p.name}, ${p.age}`),
    h("span", { class: "job" }, p.current_role ? roleTitle(p.current_role) : t("s1_student")),
    h("span", { class: "story" }, loc(p.headline)),
    h("span", { class: "go" }, t("see_results"))));
  const features = [["trend", "feat1_t", "feat1_d", "#/trends"], ["target", "feat2_t", "feat2_d", "#/start?step=1"], ["award", "feat3_t", "feat3_d", "#/learn"]].map(([ic, title, desc, href]) =>
    h("a", { class: "card feature", href }, h("span", { class: "icon-circle" }, icon(ic)), h("h3", {}, t(title)),
      h("p", {}, t(desc, { posts: hn.posts.toLocaleString(), n: state.courses?.length || 44 }))));
  const heroCard = h("div", { class: "hero-card" },
    h("h3", {}, t("hero_card_title")),
    h("p", { class: "small muted" }, t("hero_card_sub")),
    h("a", { class: "btn btn-primary btn-lg btn-block", href: "#/start?step=1", style: { marginTop: "20px" } }, t("hero_start")),
    h("div", { class: "divider" }, t("or")),
    cvInput("cvHome"),
    h("label", { class: "btn btn-secondary btn-block", for: "cvHome" }, icon("upload"), t("hero_cv")),
    h("p", { style: { textAlign: "center", marginTop: "14px" } }, h("a", { class: "btn-link", href: "#/", onclick: (e) => { e.preventDefault(); $("examples").scrollIntoView({ behavior: "smooth" }); } }, t("hero_example"))));
  return h("div", {},
    h("section", { class: "hero" }, h("div", { class: "container hero-grid" },
      h("div", {}, h("h1", {}, t("hero_title")), h("p", { class: "lead" }, t("hero_lead"))), heroCard)),
    h("section", { class: "band" }, h("div", { class: "container grid-3" }, features)),
    h("section", { class: "band band-white" }, h("div", { class: "container" },
      h("div", { class: "band-head" }, h("h2", {}, t("now_title")), h("p", {}, t("now_sub", { date: dateLabel(hn.fetched_at) }))),
      h("div", { class: "grid-2" },
        h("div", { class: "card card-top", style: { borderTopColor: "var(--blue)" } }, h("h3", {}, t("rising")), trendRows(sorted.slice(0, 5))),
        h("div", { class: "card card-top", style: { borderTopColor: "var(--orange)" } }, h("h3", {}, t("falling")), trendRows(sorted.slice(-5).reverse()))),
      h("p", { class: "source-line" }, h("a", { class: "btn-link", href: "#/trends" }, `${t("see_trends")} →`)))),
    h("section", { class: "band", id: "examples" }, h("div", { class: "container" },
      h("div", { class: "band-head" }, h("h2", {}, t("examples_title")), h("p", {}, t("examples_sub"))),
      h("div", { class: "examples" }, examples))),
    h("section", { class: "band band-tint" }, h("div", { class: "container row", style: { gap: "24px", justifyContent: "space-between" } },
      h("div", { style: { maxWidth: "560px" } }, h("h3", {}, t("sdg_band_t")), h("p", { class: "muted", style: { marginTop: "6px" } }, t("sdg_band_d"))),
      h("div", { class: "sdg-strip" }, state.meta.sdg_goals.map((g) => sdgBadge(g.goal, false))))));
}

// ---------------------------------------------------------------- Wizard
function stepsBar(step) {
  return h("div", { class: "steps" }, h("span", {}, t("step_of", { n: step })), [1, 2, 3].map((n) => h("span", { class: `bar ${n <= step ? "on" : ""}` })));
}

function jobMatches(query) {
  const q = query.trim().toLowerCase();
  if (!q) return [];
  return state.meta.roles.filter((r) => [r.title.en, loc(r.title)].some((x) => x.toLowerCase().includes(q))).slice(0, 6);
}

function isStudentQuery(query) {
  const q = query.trim().toLowerCase();
  return q.length > 2 && ["student", "graduate", "pelajar", "graduan", "学生", "毕业"].some((w) => w.includes(q) || q.includes(w));
}

function suggestionList() {
  const list = h("div", {});
  list.fill = (q) => {
    if (!q.trim()) { list.replaceChildren(); return; }
    const found = jobMatches(q);
    const student = isStudentQuery(q);
    if (!found.length && !student) { list.replaceChildren(h("p", { class: "small muted", style: { marginTop: "10px" } }, t("s1_noresult"))); return; }
    const option = (label, onclick) => h("button", { type: "button", role: "option", onclick }, h("span", {}, label), h("span", { class: "hint" }, "→"));
    list.replaceChildren(h("div", { class: "suggest", role: "listbox" },
      found.map((r) => option(loc(r.title), () => chooseJob(r.id))),
      student ? option(t("s1_student"), () => { state.wizard.student = true; render(); }) : null));
  };
  list.fill(state.wizard.query);
  return list;
}

function wizardStep1() {
  if (state.wizard.student) {
    return [h("h1", {}, t("study_title")), h("p", { class: "sub" }, t("study_sub")),
      h("div", { class: "tiles" }, state.meta.study_fields.map((f) => h("button", { type: "button", class: "tile", onclick: () => chooseField(f) }, loc(f.label)))),
      h("div", { class: "wizard-actions" }, h("button", { type: "button", class: "btn btn-link", onclick: () => { state.wizard.student = false; render(); } }, `← ${t("back")}`))];
  }
  const list = suggestionList();
  const input = h("input", { type: "search", placeholder: t("s1_search"), "aria-label": t("s1_search"), value: state.wizard.query, autocomplete: "off",
    oninput: (e) => { state.wizard.query = e.target.value; list.fill(e.target.value); },
    onkeydown: (e) => { if (e.key === "Enter") { const first = jobMatches(state.wizard.query)[0]; if (first) chooseJob(first.id); } } });
  return [
    h("h1", {}, t("s1_title")), h("p", { class: "sub" }, t("s1_sub")),
    h("div", { class: "search" }, icon("search"), input), list,
    h("div", { class: "label" }, t("s1_popular")),
    h("div", { class: "chips" },
      POPULAR_JOBS.filter((id) => roleById()[id]).map((id) => h("button", { type: "button", class: "chip", onclick: () => chooseJob(id) }, roleTitle(id))),
      h("button", { type: "button", class: "chip", onclick: () => { state.wizard.student = true; render(); } }, t("s1_student"))),
    h("div", { class: "or" }, t("or")),
    h("div", { class: "row", style: { gap: "12px" } }, cvInput("cvWizard"),
      h("label", { class: "btn btn-secondary", for: "cvWizard" }, state.wizard.busy ? h("span", { class: "spinner" }) : icon("upload"), state.wizard.busy ? t("cv_reading") : t("s1_cv")),
      h("span", { class: "small muted" }, t("s1_cv_hint"))),
    h("div", { class: "label" }, t("s1_example")),
    h("div", { class: "chips" }, state.personas.map((p) => h("button", { type: "button", class: "chip", onclick: () => { loadPersona(p); go("#/results"); } },
      `${p.name} · ${p.current_role ? roleTitle(p.current_role) : t("s1_student")}`))),
  ];
}

function suggestSkills() {
  const selected = new Set(Object.keys(state.profile.skills));
  const score = {};
  for (const sid of selected) {
    for (const [other, w] of Object.entries(skillById()[sid]?.related || {})) if (!selected.has(other)) score[other] = (score[other] || 0) + w;
  }
  POPULAR_SKILLS.forEach((sid, i) => { if (!selected.has(sid)) score[sid] = (score[sid] || 0) + 0.3 - i * 0.02; });
  return Object.entries(score).sort((a, b) => b[1] - a[1]).slice(0, 8).map(([sid]) => sid);
}

function toggleSkill(sid) {
  if (state.profile.skills[sid]) delete state.profile.skills[sid];
  else state.profile.skills[sid] = 2;
  saveProfile();
  render();
}

function skillSearchHits() {
  const q = state.wizard.skillQuery.trim().toLowerCase();
  if (!q) return [];
  return state.meta.skills.filter((x) => !state.profile.skills[x.id] && (loc(x.name).toLowerCase().includes(q) || (x.short || "").toLowerCase().includes(q))).slice(0, 10);
}

function wizardStep2() {
  const o = state.origin || {};
  const caption = { job: () => t("s2_from_job", { job: roleTitle(o.id) }), field: () => t("s2_from_field", { field: originLabel() }), cv: () => t("s2_from_cv") }[o.type];
  const note = state.wizard.cvNote;
  const selected = Object.keys(state.profile.skills);
  const hits = h("div", { class: "chips", style: { marginTop: "10px" } });
  const fillHits = () => hits.replaceChildren(...skillSearchHits().map((x) => h("button", { type: "button", class: "chip add", onclick: () => { state.wizard.skillQuery = ""; toggleSkill(x.id); } }, skillShort(x.id))));
  fillHits();
  const search = state.wizard.searchOpen
    ? [h("div", { class: "search", style: { marginTop: "16px" } }, icon("search"),
        h("input", { type: "search", placeholder: t("s2_search"), value: state.wizard.skillQuery, oninput: (e) => { state.wizard.skillQuery = e.target.value; fillHits(); } })), hits]
    : h("button", { type: "button", class: "btn btn-link", style: { marginTop: "12px" }, onclick: () => { state.wizard.searchOpen = true; render(); } }, t("s2_search"));
  return [
    h("h1", {}, t("s2_title")), h("p", { class: "sub" }, t("s2_sub")),
    caption ? h("div", { class: "label" }, caption()) : h("div", { style: { height: "20px" } }),
    note && note.engine === "llm" ? h("p", { class: "small muted", style: { marginBottom: "8px" } }, t("cv_engine_llm")) : null,
    note && note.rejected_by_guardrail ? h("p", { class: "small muted", style: { marginBottom: "8px" } }, t("cv_rejected", { n: note.rejected_by_guardrail })) : null,
    h("div", { class: "chips" }, selected.map((sid) => h("button", { type: "button", class: "chip on", "aria-pressed": "true", onclick: () => toggleSkill(sid) },
      skillShort(sid), h("span", { class: "x", "aria-hidden": "true" }, "✕")))),
    selected.length ? null : h("p", { class: "small muted", style: { marginTop: "10px" } }, t("s2_none")),
    h("div", { class: "label" }, t("s2_add")),
    h("div", { class: "chips" }, suggestSkills().map((sid) => h("button", { type: "button", class: "chip add", onclick: () => toggleSkill(sid) }, skillShort(sid)))),
    search,
    h("div", { class: "wizard-actions" },
      h("button", { type: "button", class: "btn btn-primary btn-lg", disabled: !selected.length, onclick: () => { state.wizard.step = 3; render(); } }, t("continue")),
      h("button", { type: "button", class: "btn btn-link", onclick: () => { state.wizard.step = 1; render(); } }, `← ${t("back")}`)),
  ];
}

function wizardStep3() {
  const finish = () => {
    const chosen = state.meta.interest_tiles.filter((x) => state.tiles.includes(x.id));
    state.profile.interests = [...new Set(chosen.flatMap((x) => x.tags))];
    state.profile.sdg_priorities = [...new Set(chosen.flatMap((x) => x.sdgs))];
    saveProfile();
    go("#/results");
  };
  const tiles = state.meta.interest_tiles.map((tile) => {
    const on = state.tiles.includes(tile.id);
    return h("button", { type: "button", class: `tile ${on ? "on" : ""}`, "aria-pressed": String(on),
      onclick: () => { state.tiles = on ? state.tiles.filter((x) => x !== tile.id) : [...state.tiles, tile.id]; store.set("tiles", state.tiles); render(); } },
    icon(tile.icon), loc(tile.label));
  });
  return [
    h("h1", {}, t("s3_title")), h("p", { class: "sub" }, t("s3_sub")),
    h("div", { class: "tiles" }, tiles),
    h("div", { class: "label" }, t("s3_time")),
    h("div", { class: "seg", role: "group" }, [3, 6, 10].map((n) => h("button", { type: "button", "aria-pressed": String(state.profile.hours_per_week === n),
      onclick: () => { state.profile.hours_per_week = n; saveProfile(); render(); } }, t("hours_opt", { h: n })))),
    h("div", { class: "wizard-actions" },
      h("button", { type: "button", class: "btn btn-primary btn-lg", onclick: finish }, t("s3_go")),
      h("button", { type: "button", class: "btn btn-link", onclick: () => { state.wizard.step = 2; render(); } }, `← ${t("back")}`)),
  ];
}

function viewStart() {
  const step = state.wizard.step;
  const body = step === 1 ? wizardStep1() : step === 2 ? wizardStep2() : wizardStep3();
  return h("div", { class: "container" }, h("section", { class: "wizard" }, stepsBar(step), body));
}

// ---------------------------------------------------------------- Results
function timeToReady(hours) {
  const weeks = Math.max(1, Math.ceil(hours / (state.profile.hours_per_week || 6)));
  return weeks <= 8 ? t("weeks_short", { n: weeks }) : t("months", { n: Math.round(weeks / 4.33) });
}

function paceSwitch() {
  return h("div", { class: "row", style: { gap: "10px" } }, h("span", { class: "small muted" }, t("pace_label")),
    h("div", { class: "seg", role: "group", "aria-label": t("pace_label") }, ["slow", "moderate", "fast"].map((id) => h("button", {
      type: "button", "aria-pressed": String(state.scenario === id), title: state.meta.scenarios.find((s) => s.id === id)?.description,
      onclick: () => { state.scenario = id; render(); } }, t(`pace_${id}`)))));
}

function demandValue(pct) {
  const arrow = pct > 1 ? "▲ +" : pct < -1 ? "▼ −" : "";
  const abs = Math.abs(pct);
  return `${arrow}${abs < 10 ? abs.toFixed(1) : Math.round(abs)}%`;
}

function matchDetails(r, role) {
  const exp = state.explanations[r.id];
  const have = r.items.filter((i) => i.status === "have");
  const learn = r.items.filter((i) => i.status !== "have").sort((a, b) => b.weight - a.weight);
  const engine = exp?.engine === "llm" ? t("engine_llm", { model: exp.model }) : exp?.guardrail?.rejected ? t("guard_rejected") : t("engine_template");
  return h("div", { class: "details" },
    h("h4", {}, t("d_explain")),
    h("div", { class: "explain" }, h("p", {}, exp?.text || r.explanation), h("p", { class: "engine-note" }, engine),
      state.meta.llm?.online ? h("button", { type: "button", class: "btn btn-secondary btn-sm", style: { marginTop: "8px" }, onclick: (e) => explainWithAI(r.id, e.currentTarget) }, t("explain_ai")) : null),
    have.length ? [h("h4", {}, t("d_have")), h("div", { class: "row" }, have.map((i) => h("span", { class: "pill have" }, "✓ ", skillShort(i.id))))] : null,
    learn.length ? [h("h4", {}, t("d_learn")), h("div", { class: "row" }, learn.map((i) => h("a", { class: "pill learn", href: `#/learn/${i.id}` }, `${skillShort(i.id)} · ${i.gap_hours} h`)))] : null,
    h("h4", {}, t("d_scen")),
    h("div", { class: "scen-bars" }, ["slow", "moderate", "fast"].map((k) => h("div", { class: `scen-bar ${k === state.scenario ? "active" : ""}`,
      title: `${t("range")} ${fmtPct(r.outlook[k].low)} … ${fmtPct(r.outlook[k].high)}` },
    h("span", {}, t(`pace_${k}`)), miniBar(r.outlook[k]), h("span", { class: "num" }, fmtPct(r.outlook[k].pct))))),
    h("h4", {}, t("d_sdg")),
    role.sdgs.map((x) => h("div", { class: "row", style: { gap: "10px", flexWrap: "nowrap", alignItems: "flex-start", marginTop: "6px" } },
      sdgBadge(x.goal, true, state.meta.sdg_targets[x.target]), h("span", { class: "small" }, h("b", {}, `${x.target} `), x.why))),
    (r.sources || []).length ? [h("h4", {}, t("d_sources")), h("ol", { class: "sources" }, r.sources.map((x) =>
      h("li", {}, x.url ? h("a", { href: x.url, target: "_blank", rel: "noopener" }, x.label) : x.label)))] : null);
}

function matchCard(r) {
  const role = roleById()[r.id];
  const o = r.outlook[state.scenario];
  const open = !!state.expanded[r.id];
  const goals = [...new Set(role.sdgs.map((x) => x.goal))];
  return h("article", { class: "match-card", style: { "--fam": `var(--fam-${role.family})` } },
    (r.rank === 1 || r.robust) ? h("div", { class: "match-head", style: { marginBottom: "8px" } },
      r.rank === 1 ? h("span", { class: "badge best" }, t("best")) : null,
      r.robust ? h("span", { class: "badge robust" }, `◆ ${t("robust")}`) : null) : null,
    h("div", { class: "match-head" }, h("h3", {}, roleTitle(r.id))),
    h("p", { class: "match-sub" }, role.summary),
    h("div", { class: "stats" },
      h("div", { class: "stat" }, h("div", { class: "v" }, `${r.fit}%`), h("div", { class: "k" }, t("stat_fit"))),
      h("div", { class: "stat" }, h("div", { class: `v ${o.pct > 1 ? "up" : o.pct < -1 ? "down" : ""}` }, demandValue(o.pct)), h("div", { class: "k" }, t("stat_demand"))),
      h("div", { class: "stat" }, h("div", { class: "v" }, timeToReady(r.plan_hours ?? r.gap_hours)), h("div", { class: "k" }, t("stat_time")))),
    h("div", { class: "match-actions" },
      h("a", { class: "btn btn-primary", href: `#/plan/${r.id}` }, t("see_plan")),
      h("button", { type: "button", class: "btn btn-link", "aria-expanded": String(open), onclick: () => { state.expanded[r.id] = !open; render(); } }, open ? t("hide") : t("why")),
      h("span", { class: "spacer" }),
      h("span", { class: "row", style: { gap: "4px" } }, goals.map((goal) =>
        sdgBadge(goal, true, role.sdgs.filter((x) => x.goal === goal).map((x) => `${x.target}: ${x.why}`).join("\n"))))),
    open ? matchDetails(r, role) : null);
}

async function explainWithAI(rid, btn) {
  btn.disabled = true;
  btn.textContent = t("explaining");
  try {
    state.explanations[rid] = await api("/api/explain", { as_of: state.asOf, scenario: state.scenario, lang: state.lang, profile: state.profile, weights: state.weights, role_id: rid });
  } catch (e) { toast(String(e.message || e)); }
  render();
}

function startPrompt() {
  return h("div", { class: "container" }, h("section", { class: "wizard", style: { textAlign: "center" } },
    h("h1", {}, t("start_title")), h("p", { class: "sub" }, t("start_sub")),
    h("div", { class: "wizard-actions", style: { justifyContent: "center" } }, h("a", { class: "btn btn-primary btn-lg", href: "#/start?step=1" }, t("hero_start")))));
}

function weightSlider(key, label) {
  const out = h("b", { class: "num" }, `${Math.round(state.weights[key] * 100)}`);
  return h("label", { style: { display: "block" } },
    h("span", { class: "row", style: { justifyContent: "space-between" } }, h("span", { class: "small" }, label), out),
    h("input", { type: "range", min: 0, max: 100, value: Math.round(state.weights[key] * 100), style: { width: "100%", accentColor: "var(--blue)" },
      oninput: (e) => { out.textContent = e.target.value; }, onchange: (e) => { state.weights[key] = Number(e.target.value) / 100; render(); } }));
}

function viewResults() {
  if (!hasProfile()) return startPrompt();
  const m = state.matches;
  const cur = m.current;
  let notice = null;
  if (cur) {
    const pct = cur.outlook[state.scenario].pct;
    if (pct < -1) notice = h("div", { class: "notice" }, t("alert_down", { role: roleTitle(cur.id), pct: Math.abs(pct).toFixed(0) }));
    else if (pct > 1) notice = h("div", { class: "notice good" }, t("alert_up", { role: roleTitle(cur.id), pct: pct.toFixed(0) }));
  }
  const moved = m.changes ? m.changes.roles.filter((r) => r.rank <= 3 && r.prev_rank !== r.rank) : [];
  const rest = m.roles.slice(3, 8);
  const moreList = h("div", { class: "card more-list", style: { marginTop: "16px" } }, rest.map((r) => h("div", { class: "row-item" },
    h("span", { class: "t" }, `${r.rank}. ${roleTitle(r.id)}`), h("span", { class: "small" }, `${r.fit}% ${t("stat_fit")}`),
    trendSpan(r.outlook[state.scenario].pct, ` ${t("per_year")}`), h("a", { class: "btn btn-secondary btn-sm", href: `#/plan/${r.id}` }, t("see_plan")))));
  return h("div", {},
    h("section", { class: "page-head" }, h("div", { class: "container" },
      h("h1", {}, t("res_title")), h("p", {}, t("res_sub")),
      h("div", { class: "summary-bar" },
        h("span", { class: "based" }, t("based_on", { label: originLabel(), n: Object.keys(state.profile.skills).length }), " · ",
          h("a", { href: "#/start?step=2" }, t("edit"))),
        h("span", { class: "spacer" }), paceSwitch()))),
    h("section", { class: "band", style: { paddingTop: "28px" } }, h("div", { class: "container", style: { maxWidth: "920px" } },
      notice ? h("div", { style: { marginBottom: "20px" } }, notice) : null,
      moved.length ? h("p", { class: "small muted", style: { marginBottom: "14px" } }, `${t("changes", { month: monthLabel(m.as_of) })} `,
        moved.map((r, i) => [i ? " · " : "", `${roleTitle(r.id)} ${r.prev_rank > r.rank ? "▲" : "▼"}${Math.abs(r.prev_rank - r.rank)}`])) : null,
      m.roles.slice(0, 3).map(matchCard),
      rest.length ? h("div", { style: { marginTop: "20px", textAlign: "center" } },
        h("button", { type: "button", class: "btn btn-secondary", onclick: () => { state.showMore = !state.showMore; render(); } },
          state.showMore ? t("fewer_roles") : t("more_roles", { n: rest.length }))) : null,
      state.showMore ? moreList : null,
      h("details", { class: "card", style: { marginTop: "24px" } }, h("summary", { style: { cursor: "pointer", fontWeight: "700" } }, t("adjust")),
        h("div", { class: "grid-3", style: { marginTop: "16px", gap: "20px" } }, weightSlider("fit", t("w_fit")), weightSlider("outlook", t("w_outlook")), weightSlider("preference", t("w_pref")))),
      h("p", { class: "source-line", style: { textAlign: "center", marginTop: "24px" } },
        t("res_foot", { date: dateLabel(state.meta.signals.hn.fetched_at) }), " ", h("a", { href: "#/how" }, t("how_link"))))));
}

// ---------------------------------------------------------------- Plan
function planStep(rid, st, progress) {
  const cert = state.certs[st.skill];
  const isDone = !!progress[st.skill] || !!cert;
  const openOpts = !!state.openOpts[st.skill];
  const res = st.resource;
  const hasMore = st.alternatives.length || st.credential || st.practice;
  const minutes = courseMinutes(st.skill);
  const learnHere = cert
    ? h("a", { class: "badge robust", href: `#/certificate/${cert.token}` }, `✓ ${t("certified")}`)
    : h("a", { class: "btn btn-primary btn-sm", href: `#/learn/${st.skill}` }, icon("book"), minutes ? t("learn_here", { m: minutes }) : t("nav_learn"));
  const course = res
    ? h("div", { class: "course" },
        h("div", { style: { flex: "1", minWidth: "200px" } }, h("div", { class: "tiny muted" }, t("then_course")), h("div", { class: "c-title" }, res.title),
          h("div", { class: "c-sub" }, `${res.provider} · ~${res.hours} h `, costTag(res.cost))),
        h("a", { class: "btn btn-secondary btn-sm", href: res.url, target: "_blank", rel: "noopener" }, `${t("open_course")} ↗`))
    : h("div", { class: "course" }, h("span", { class: "small" }, t("no_resource")));
  const options = openOpts ? h("div", { class: "details small" },
    st.alternatives.length ? [h("h4", {}, t("alts")), h("ul", { class: "sources" }, st.alternatives.map((a) => h("li", {}, h("a", { href: a.url, target: "_blank", rel: "noopener" }, a.title), ` · ${a.provider} · `, costTag(a.cost))))] : null,
    st.credential ? [h("h4", {}, t("cred")), h("p", {}, h("a", { href: st.credential.url, target: "_blank", rel: "noopener" }, st.credential.title), " · ", costTag(st.credential.cost))] : null,
    st.practice ? [h("h4", {}, t("practice")), h("p", {}, st.practice)] : null,
    st.sdgs.length ? h("div", { class: "row", style: { marginTop: "10px" } }, st.sdgs.map((x) => h("span", { class: "row", style: { gap: "6px" } }, sdgBadge(x.goal, true), `${x.target} ${x.why}`))) : null) : null;
  return h("div", { class: `plan-step ${isDone ? "done" : ""}` },
    h("div", { class: "step-num" }, isDone ? "✓" : String(st.n)),
    h("div", { class: "step-card" },
      h("div", { class: "tiny muted" }, t("step_n", { n: st.n }).toUpperCase()),
      h("h3", {}, skillName(st.skill)),
      h("div", { class: "step-meta" }, t("step_meta", { h: st.hours, a: st.week_start, b: st.week_end })),
      h("div", { class: "row", style: { marginTop: "12px" } }, learnHere),
      course,
      h("div", { class: "step-foot" },
        cert ? null : h("label", { class: "check" }, h("input", { type: "checkbox", checked: isDone,
          onchange: (e) => { state.progress[rid] = { ...progress, [st.skill]: e.target.checked }; store.set("progress", state.progress); render(); } }), t("mark_done")),
        hasMore ? h("button", { type: "button", class: "btn btn-link", onclick: () => { state.openOpts[st.skill] = !openOpts; render(); } }, openOpts ? t("fewer_opts") : t("more_opts")) : null),
      options));
}

function viewPlan(rid) {
  if (!hasProfile()) return startPrompt();
  if (!rid || !roleById()[rid]) return h("div", { class: "container" }, h("p", { class: "notice info", style: { marginTop: "32px" } }, t("plan_choose")));
  const p = state.pathway;
  const progress = state.progress[rid] || {};
  const done = p.steps.filter((st) => progress[st.skill] || state.certs[st.skill]).length;
  const allFree = p.steps.length && p.steps.every((st) => !st.resource || st.resource.cost === "free");
  const impact = h("div", { class: "card" }, h("h3", { style: { marginBottom: "14px" } }, t("impact_t")),
    h("div", { class: "impact" }, p.sdg_contribution.slice(0, 3).map((c) => h("div", { class: "impact-item" }, sdgBadge(c.goal, false),
      h("div", {}, h("b", {}, loc(goalOf(c.goal).name)), h("div", { class: "small muted" }, c.targets[0] ? `${c.targets[0].target} · ${c.targets[0].why}` : ""))))));
  const support = h("div", { class: "card" }, h("h3", {}, t("final_t")),
    p.capstone.practice ? h("p", { class: "small", style: { marginTop: "8px" } }, h("b", {}, `${t("practice")}: `), p.capstone.practice) : null,
    h("h4", { style: { margin: "16px 0 6px", fontSize: "14px" } }, t("final_support")),
    h("ul", { class: "sources" }, p.capstone.support.map((x) => h("li", {}, h("a", { href: x.url, target: "_blank", rel: "noopener" }, x.title)))));
  return h("div", {},
    h("section", { class: "page-head" }, h("div", { class: "container" },
      h("p", { class: "no-print", style: { marginBottom: "10px" } }, h("a", { href: "#/results" }, `← ${t("back_results")}`)),
      h("h1", {}, t("plan_title", { role: roleTitle(rid) })),
      h("p", {}, t("plan_sum", { n: p.steps.length, hours: p.total_hours, weeks: p.weeks, hpw: p.hours_per_week }), allFree ? ` · ${t("plan_free")}` : ""),
      h("div", { class: "progress", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": p.steps.length, "aria-valuenow": done },
        h("span", { style: { width: `${p.steps.length ? (done / p.steps.length) * 100 : 0}%` } })),
      h("p", { class: "small muted", style: { marginTop: "6px" } }, t("plan_progress", { done, n: p.steps.length })))),
    h("section", { class: "band", style: { paddingTop: "28px" } }, h("div", { class: "container grid-main" },
      h("div", {}, p.steps.map((st) => planStep(rid, st, progress))),
      h("div", { class: "stack" }, impact, support,
        h("button", { type: "button", class: "btn btn-secondary btn-block no-print", onclick: () => window.print() }, t("print"))))));
}

// ---------------------------------------------------------------- Explore trends
async function refreshSignals(btn) {
  state.busy = true;
  btn.disabled = true;
  btn.textContent = t("tr_refreshing");
  try {
    await api("/api/signals/refresh", {});
    for (;;) {
      await new Promise((r) => setTimeout(r, 1500));
      const st = await api("/api/signals/status");
      if (st.state !== "running") {
        state.meta = await api("/api/meta");
        state.asOf = state.meta.as_of_default;
        state.radarKey = ""; state.matchesKey = ""; state.teamKey = ""; state.pathwayKey = "";
        const bad = Object.entries(st.result || {}).filter(([, v]) => v !== "ok");
        toast(bad.length ? `${t("tr_refreshed")} · ${bad.map(([k, v]) => `${k}: ${v}`).join("; ")}` : t("tr_refreshed"));
        break;
      }
    }
  } catch (e) { toast(String(e.message || e)); }
  state.busy = false;
  render();
}

async function selectSkill(id) {
  state.skillDetail = await api(`/api/skill/${id}?as_of=${state.asOf}`);
  render();
}

function viewTrends() {
  const d = state.radar;
  const names = Object.fromEntries(state.meta.skills.map((x) => [x.id, loc(x.name)]));
  const shorts = Object.fromEntries(state.meta.skills.map((x) => [x.id, skillShort(x.id)]));
  const mine = new Set(Object.keys(state.profile.skills));
  const sorted = d.skills.slice().sort((a, b) => b.pct - a.pct);
  const bars = (list) => divergingBars(list.map((x) => ({ label: shorts[x.id], value: x.pct, low: x.low, high: x.high,
    tip: () => h("div", {}, h("div", { class: "v" }, `${fmtPct(x.pct)} ${t("per_year")}`), h("div", { class: "k" }, names[x.id]),
      h("div", { class: "k" }, `${t("range")} ${fmtPct(x.low)} … ${fmtPct(x.high)} · ${t(`conf_${x.confidence}`)}`)) })), { domain: [-30, 60] });
  const seg = h("div", { class: "seg" }, ["radar", "table"].map((v) => h("button", { type: "button", "aria-pressed": String(state.radarView === v), onclick: () => { state.radarView = v; render(); } }, t(`view_${v}`))));
  const legend = h("div", { class: "legend" }, ["surging", "rising", "stable", "declining"].map((r) => h("span", { class: "key" }, h("span", { class: "sw", style: { background: `var(--t-${r})` } }), t(`ring_${r}`))),
    mine.size ? h("span", { class: "key" }, h("span", { class: "sw mine" }), t("your_skill")) : null);
  const table = h("div", { style: { overflowX: "auto" } }, h("table", { class: "data" },
    h("thead", {}, h("tr", {}, [t("th_skill"), t("th_cat"), t("th_est"), t("th_range"), t("th_conf"), t("th_drivers")].map((x) => h("th", {}, x)))),
    h("tbody", {}, sorted.map((r) => h("tr", { style: { cursor: "pointer" }, onclick: () => selectSkill(r.id) },
      h("td", {}, names[r.id]), h("td", {}, loc(state.meta.categories[r.category])), h("td", { class: "n" }, trendSpan(r.pct)),
      h("td", { class: "n" }, `${fmtPct(r.low)} … ${fmtPct(r.high)}`), h("td", {}, t(`conf_${r.confidence}`)),
      h("td", { class: "small" }, `${t("comp_market")} ${fmtPct(r.components.market)} · ${t("comp_prior")} ${fmtPct(r.components.prior)} · ${t("comp_ai")} ${fmtPct(r.components.ai)}`))))));
  const chart = state.radarView === "radar"
    ? h("div", {}, radar({ skills: d.skills, categories: state.meta.categories, names, shorts, mine, t, lang: state.lang, onSelect: selectSkill }), legend)
    : table;
  const caps = d.capabilities.filter((c) => c.available).sort((a, b) => b.momentum_pct - a.momentum_pct);
  const pulse = divergingBars(caps.map((c) => ({ label: c.label, value: c.momentum_pct,
    tip: () => h("div", {}, h("div", { class: "v" }, fmtPct(c.momentum_pct)), h("div", { class: "k" }, `${c.bucket_base}: ${c.count_base.toLocaleString()} → ${c.bucket_recent}: ${c.count_recent.toLocaleString()} works`)) })), { domain: [-60, 120] });
  const sig = state.meta.signals;
  const det = state.skillDetail;
  const detail = det ? h("div", { class: "card" }, h("h3", {}, names[det.id]), h("p", { class: "small muted" }, t(`conf_${det.confidence}`)),
    h("div", { style: { margin: "12px 0" } }, divergingBars(Object.entries(det.by_scenario).map(([k, v]) => ({ label: t(`pace_${k}`), value: v.pct, low: v.low, high: v.high })), { domain: [-30, 60] })),
    det.sparkline.length ? [h("p", { class: "tiny muted" }, t("spark_t")), sparkline(det.sparkline)] : null,
    h("a", { class: "btn btn-secondary btn-sm", href: `#/learn/${det.id}`, style: { marginTop: "10px" } }, icon("book"), t("nav_learn"))) : null;
  const sources = h("div", { class: "card small" }, h("h3", { style: { marginBottom: "10px" } }, t("src_t")),
    h("p", {}, h("b", {}, "Hacker News · Who is hiring?"), h("br"), `${monthLabel(sig.hn.first_month)} – ${monthLabel(sig.hn.last_month)} · ${sig.hn.posts.toLocaleString()} job posts · ${dateLabel(sig.hn.fetched_at)}`),
    h("p", { style: { marginTop: "8px" } }, h("b", {}, "OpenAlex"), h("br"), `${sig.openalex.buckets.join(", ")} · ${dateLabel(sig.openalex.fetched_at)}`),
    h("p", { style: { marginTop: "8px" } }, h("b", {}, "WEF Future of Jobs 2025 / 2023"), h("br"), "baseline priors (cited list membership)"));
  return h("div", {},
    h("section", { class: "page-head" }, h("div", { class: "container" },
      h("h1", {}, t("tr_title")), h("p", {}, t("tr_sub")),
      h("div", { class: "controls" },
        h("label", {}, t("tr_asof"), h("select", { onchange: (e) => { state.asOf = e.target.value; state.matchesKey = ""; state.pathwayKey = ""; state.skillDetail = null; render(); } },
          state.meta.as_of_options.map((mo) => h("option", { value: mo, selected: mo === state.asOf }, monthLabel(mo))))),
        paceSwitch(),
        h("button", { type: "button", class: "btn btn-secondary btn-sm", disabled: state.busy, onclick: (e) => refreshSignals(e.currentTarget) }, state.busy ? t("tr_refreshing") : t("tr_refresh"))))),
    h("section", { class: "band", style: { paddingTop: "28px" } }, h("div", { class: "container stack" },
      h("div", { class: "grid-2" },
        h("div", { class: "card card-top", style: { borderTopColor: "var(--blue)" } }, h("h3", { style: { marginBottom: "14px" } }, t("tr_rising")), bars(sorted.slice(0, 8))),
        h("div", { class: "card card-top", style: { borderTopColor: "var(--orange)" } }, h("h3", { style: { marginBottom: "14px" } }, t("tr_falling")), bars(sorted.slice(-8).reverse()))),
      h("div", { class: "grid-main" },
        h("div", { class: "card" }, h("div", { class: "row" }, h("div", {}, h("h3", {}, t("radar_t")), h("p", { class: "small muted" }, t("radar_sub"))), h("span", { class: "spacer" }), seg),
          h("div", { style: { marginTop: "12px" } }, chart)),
        h("div", { class: "stack" }, detail,
          h("div", { class: "card" }, h("h3", {}, t("pulse_t")), h("p", { class: "tiny muted", style: { margin: "4px 0 12px" } }, t("pulse_sub", { base: d.bucket_base, recent: d.bucket_recent })), pulse),
          sources)))));
}

// ---------------------------------------------------------------- Teams
function viewTeams() {
  const d = state.team;
  const head = h("tr", {}, h("th", {}, t("tm_member")), h("th", {}, t("tm_current")),
    d.targets.map((rid) => h("th", {}, roleTitle(rid), h("div", { class: "tiny" }, trendSpan(d.target_outlook[rid], ` ${t("per_year")}`)))));
  const rows = d.members.map((m) => h("tr", {},
    h("td", { class: "lbl" }, m.alias),
    h("td", { class: "lbl" }, roleTitle(m.current_role), h("div", {}, trendSpan(m.current_outlook_pct, ` ${t("per_year")}`))),
    d.targets.map((rid) => {
      const col = heatColor(m.fits[rid]);
      return h("td", { class: m.best === rid ? "best" : "", style: { background: col.bg, color: col.fg }, title: `${m.alias} → ${roleTitle(rid)}: ${m.fits[rid]}%` }, `${m.fits[rid]}%`);
    })));
  const gaps = magnitudeBars(d.skill_gaps.slice(0, 8).map((g) => ({ label: h("span", {}, skillShort(g.skill), " ", h("span", { class: "tiny" }, trendSpan(g.outlook_pct))),
    value: g.members, display: t("tm_people", { n: g.members }) })), { max: d.members.length });
  return h("div", {},
    h("section", { class: "page-head" }, h("div", { class: "container" }, h("h1", {}, t("tm_title")), h("p", {}, t("tm_sub")), h("div", { class: "controls" }, paceSwitch()))),
    h("section", { class: "band", style: { paddingTop: "28px" } }, h("div", { class: "container stack" },
      h("div", { class: "card" }, h("h3", { style: { marginBottom: "12px" } }, d.name), h("div", { style: { overflowX: "auto" } }, h("table", { class: "heat" }, h("thead", {}, head), h("tbody", {}, rows)))),
      h("div", { class: "card" }, h("h3", { style: { marginBottom: "12px" } }, t("tm_gaps")), gaps))));
}

// ---------------------------------------------------------------- How it works (methodology, English)
function viewHow() {
  const m = state.meta;
  const model = m.model;
  const card = (title, ...body) => h("div", { class: "card prose" }, h("h3", { style: { marginBottom: "8px" } }, title), ...body);
  const steps = [
    ["1 · You", "Pick your job, field of study or upload a CV. We pre-fill typical skills; you confirm them."],
    ["2 · Live signals", `${m.signals.hn.posts.toLocaleString()} job posts (HN Who is hiring) + AI-research volume (OpenAlex) + cited WEF baselines.`],
    ["3 · Forecast", "Per skill: job-post momentum + baseline + AI pressure × scenario pace (slower 0.5 / expected 1 / faster 2), with a range."],
    ["4 · Match", "Skills fit (incl. transferable skills) · future demand · your interests and SDGs. Robust = top 5 in every scenario."],
    ["5 · Learn + certify", `A free micro-course for every skill (3 lessons + quiz), a verifiable Path.AI certificate, and ${m.resources.count} verified external courses.`],
  ];
  return h("div", {},
    h("section", { class: "page-head" }, h("div", { class: "container" }, h("h1", {}, t("how_title")),
      h("p", {}, "From live signals to a personal plan — transparent, cited and with people in charge."))),
    h("section", { class: "band", style: { paddingTop: "28px" } }, h("div", { class: "container stack" },
      h("div", { class: "pipeline" }, steps.map(([a, b]) => h("div", { class: "card" }, h("b", {}, a), h("p", { class: "small", style: { marginTop: "6px" } }, b)))),
      h("div", { class: "grid-2" },
        card("The forecast, in one line",
          h("p", { class: "small" }, "growth = market_weight × job-post momentum + baseline + pace × Σ sensitivity × (1 + AI capability momentum)"),
          h("ul", { class: "small" },
            h("li", {}, `market_weight = ${model.market_weight}; momentum clipped to ±${model.market_momentum_clip} and shrunk for small samples (empirical Bayes, prior sd ${model.momentum_prior_sd}).`),
            h("li", {}, `baseline = +${model.prior_step} when a cited WEF claim says the skill is rising; role priors +${model.role_prior_growing} / ${model.role_prior_declining}.`),
            h("li", {}, "AI capability momentum = year-over-year change in a topic's share of AI research (OpenAlex)."),
            h("li", {}, "Sensitivities (substitute −, complement +) are published team assumptions informed by the ILO 2025 exposure index and WEF 2025."))),
        card("Nothing is invented",
          h("ul", { class: "small" },
            h("li", {}, "Jobs come only from our role catalog (O*NET codes / WEF categories); courses only from a verified list. If nothing fits, the plan says so."),
            h("li", {}, "The AI never picks jobs, courses or numbers. When reading a CV, every skill must quote the CV word-for-word."),
            h("li", {}, "AI-written explanations must cite our sources and may only use numbers from the fact sheet — otherwise we show the verified text."))),
        card("Lessons & certificates",
          h("ul", { class: "small" },
            h("li", {}, "Each lesson combines a Path.AI note, a practical activity and a reading excerpt from Wikipedia (CC BY-SA 4.0) with full attribution and a link to the exact revision used."),
            h("li", {}, "Quizzes are graded on the server and every question is answerable from the lessons. Pass mark: 4 of 5."),
            h("li", {}, "Certificates are signed (HMAC-SHA256) and can be verified by anyone with the link; we keep no database of names. They are not accredited qualifications."))),
        card("AI model disclosure",
          h("p", { class: "small" }, m.llm.online ? `Online: ${m.llm.model} (open weights, served with vLLM).` : `Configured: ${m.llm.model || "Qwen/Qwen3.8-27B-FP8"} on a RunPod GPU — currently offline, so everything runs rule-based.`),
          h("p", { class: "small muted" }, "Rankings, trends, plans and lessons never depend on the language model.")),
        card("Fair and human-centred",
          h("p", { class: "small" }, "We use only skills, interests, SDG priorities and available time — never age, gender, ethnicity or location. You can edit every skill and re-weight the ranking. Path.AI supports career decisions; it does not make hiring decisions.")),
        card("Known limitations",
          h("ul", { class: "small" },
            h("li", {}, "HN job posts are global and tech-centric, so we use them only for tech skills; other skills rely on baselines and AI signals (marked low confidence)."),
            h("li", {}, "Research attention is a proxy for AI progress, not a measure of real-world adoption."),
            h("li", {}, "Lessons are short introductions in English; the external courses in each plan go deeper."),
            h("li", {}, "Next: Malaysian job feeds (e.g. MYFutureJobs / MyMahir), DOSM labour statistics and HRD Corp programme data.")))))));
}

// ---------------------------------------------------------------- router
function parseRoute() {
  const raw = location.hash.slice(1) || "/";
  const [path, qs] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  return { name: parts[0] || "home", arg: parts[1], params: new URLSearchParams(qs || "") };
}

// Deep links for demos, e.g.  #/results?persona=aisyah&pace=fast&lang=ms&asof=2025-10
function applyParams(params) {
  const persona = state.personas.find((p) => p.id === params.get("persona"));
  if (persona) loadPersona(persona);
  if (["en", "ms", "zh"].includes(params.get("lang"))) setLang(params.get("lang"));
  if (["slow", "moderate", "fast"].includes(params.get("pace"))) state.scenario = params.get("pace");
  if (state.meta.as_of_options.includes(params.get("asof"))) state.asOf = params.get("asof");
  if (params.get("open")) state.expanded[params.get("open")] = true;
  const step = Number(params.get("step"));
  if ([1, 2, 3].includes(step)) state.wizard = { ...state.wizard, step, student: false, searchOpen: false, skillQuery: "" };
}

let lastRoute = "";
async function render() {
  const r = parseRoute();
  renderChrome(r.name);
  certificatePrintStyle(r.name === "certificate");
  const main = $("main");
  main.classList.add("loading");
  try {
    if (r.name === "home" || r.name === "trends") await ensureRadar();
    if (r.name === "home" || r.name === "plan") await ensureCourses();
    if (r.name === "results" && hasProfile()) await ensureMatches();
    if (r.name === "plan" && hasProfile() && roleById()[r.arg]) await ensurePathway(r.arg);
    if (r.name === "teams") await ensureTeam();
    if (r.name === "learn" || r.name === "certificate") await ensureLearn(r);
    const views = { home: viewHome, start: viewStart, results: viewResults, plan: () => viewPlan(r.arg), trends: viewTrends, teams: viewTeams, how: viewHow,
      learn: () => (r.arg ? viewCourse() : viewLearn()), certificate: () => viewCertificate(r.arg) };
    main.replaceChildren((views[r.name] || viewHome)());
  } catch (e) {
    main.replaceChildren(h("div", { class: "container" }, h("p", { class: "notice", style: { marginTop: "32px" } }, String(e.message || e))));
  }
  main.classList.remove("loading");
  const routeKey = `${r.name}/${r.arg || ""}`;
  if (routeKey !== lastRoute) {
    window.scrollTo({ top: 0 });
    main.focus({ preventScroll: true });
    lastRoute = routeKey;
  }
}
setRenderer(render);

window.addEventListener("hashchange", () => {
  applyParams(parseRoute().params);
  render();
});

async function boot() {
  [state.meta, { personas: state.personas }] = await Promise.all([api("/api/meta"), api("/api/personas")]);
  state.asOf = state.meta.as_of_default;
  applyParams(parseRoute().params);
  await render();
}

boot().catch((e) => { $("main").replaceChildren(h("div", { class: "container" }, h("p", { class: "notice", style: { marginTop: "32px" } }, `Failed to load: ${e.message || e}`))); });
