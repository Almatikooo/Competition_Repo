// Career coach: a chat that knows the person's journey. Their browser sends the profile, course progress, certificates
// and ticked plan steps with each question; the server builds the facts, the model answers from them only (every
// number is checked) and may add up to three links to Path.AI pages it was offered. The conversation stays here.
import { h } from "./charts.js";
import { state, store, t, api, skillName, skillShort, roleTitle, hasProfile, icon, rerender, go, DEFAULT_LANGUAGES } from "./core.js";
import { countryName } from "./next.js";

const KEEP = 30;               // messages kept in this browser
const SEND = 12;               // messages sent with a question (the server lets the model see the latest few)
const SUGGESTED = ["coach_q_week", "chat_q_first", "chat_q_fastest", "chat_q_jobs", "coach_q_compare", "coach_q_cv", "coach_q_interview"];

const coach = () => (state.coach ||= { messages: store.get("coach", []), busy: false, pending: null });
const save = () => store.set("coach", coach().messages.slice(-KEEP));
const where = () => state.next?.country || "MY";

function context() {
  const learning = {};
  for (const [sid, p] of Object.entries(state.learned || {}).slice(0, 60)) {
    const done = (p.done || []).length, chapters = Object.keys(p.chapters || {}).length;
    if (done || chapters || p.final) learning[sid] = { done, chapters, final: !!p.final };
  }
  const plans = {};
  for (const [rid, steps] of Object.entries(state.progress || {})) {
    const ticked = Object.keys(steps).filter((k) => steps[k]).slice(0, 40);
    if (ticked.length && Object.keys(plans).length < 8) plans[rid] = ticked;
  }
  const focus = store.get("focusRole", null);              // the plan opened last
  if (focus && !plans[focus] && Object.keys(plans).length < 8) plans[focus] = [];
  return { learning, certified: Object.keys(state.certs || {}).slice(0, 60), plans };
}

async function send(text) {
  const c = coach();
  text = (text || "").trim().slice(0, 600);
  if (!text || c.busy) return;
  c.messages.push({ role: "user", content: text });
  c.busy = true;
  save();
  rerender();
  const history = c.messages.filter((m) => !m.note).slice(-SEND).map(({ role, content }) => ({ role, content: content.slice(0, 600) }));
  try {
    const res = await api("/api/chat", { as_of: state.asOf, scenario: state.scenario, lang: state.lang, weights: state.weights, country: where(),
      profile: { ...state.profile, languages: state.profile.languages || DEFAULT_LANGUAGES }, messages: history, context: context() });
    if (res.engine === "llm") c.messages.push({ role: "assistant", content: res.text, links: res.links || [] });
    else c.messages.push({ role: "assistant", note: true,
      content: t(res.guardrail?.rejected ? "chat_cant" : /busy/.test(res.error || "") ? "coach_busy" : "coach_off") });
  } catch (e) {
    c.messages.push({ role: "assistant", note: true, content: String(e.message || e) });
  }
  c.busy = false;
  save();
  rerender();
}

// Opens the coach with a question already asked (from the results page).
export function askCoach(question) {
  coach().pending = question;
  go("#/coach");
}

function linkButton(l) {
  const a = (href, label, ic, external) => h("a", { class: "btn btn-secondary btn-sm", href, ...(external ? { target: "_blank", rel: "noopener" } : {}) },
    icon(ic), label);
  if (l.kind === "plan") return a(`#/plan/${l.id}`, t("coach_link_plan", { role: roleTitle(l.id) }), "route");
  if (l.kind === "course") return a(`#/learn/${l.id}`, t("coach_link_course", { skill: skillName(l.id) }), "book");
  if (l.kind === "jobs") return a(`#/next?mode=work&country=${l.country}`, t("coach_link_jobs", { country: countryName(l.country) }), "briefcase");
  if (l.kind === "job") return a(l.url, `${l.title} · ${l.company}`, "briefcase", true);
  if (l.kind === "learn") return a("#/learn", t("coach_link_learn"), "book");
  return null;
}

// The model writes plain sentences or a few "- " lines; nothing it writes is treated as HTML.
function answerText(text) {
  const blocks = [];
  let list = null;
  for (const line of text.split("\n").map((x) => x.trim()).filter(Boolean)) {
    if (/^[-•*]\s+/.test(line)) {
      if (!list) blocks.push((list = h("ul", {})));
      list.append(h("li", {}, line.replace(/^[-•*]\s+/, "")));
    } else {
      list = null;
      blocks.push(h("p", {}, line));
    }
  }
  return blocks;
}

function message(m) {
  if (m.role === "user") return h("div", { class: "msg user" }, m.content);
  return h("div", { class: `msg assistant${m.note ? " note" : ""}` }, answerText(m.content),
    m.links?.length ? h("div", { class: "coach-links" }, m.links.map(linkButton)) : null);
}

function seesPanel() {
  const p = state.profile;
  const strongest = Object.entries(p.skills).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([id]) => skillShort(id));
  const top = (state.matches?.roles || []).slice(0, 3);
  const started = Object.values(state.learned || {}).filter((x) => (x.done || []).length).length;
  const certs = Object.keys(state.certs || {}).length;
  const focus = store.get("focusRole", null);
  const ticked = focus ? Object.values(state.progress?.[focus] || {}).filter(Boolean).length : 0;
  const llm = state.meta.llm || {};
  const row = (label, value) => h("div", { class: "row-item" }, h("span", { class: "small muted" }, label), h("span", { class: "small" }, value));
  return h("aside", { class: "card coach-sees" },
    h("h3", {}, t("coach_sees")),
    row(t("coach_job"), p.current_role ? roleTitle(p.current_role) : "–"),
    row(t("coach_skills"), strongest.join(", ") || "–"),
    top.length ? row(t("coach_top"), top.map((r) => `${roleTitle(r.id)} ${r.fit}%`).join(" · ")) : null,
    row(t("coach_learning"), t("coach_learning_v", { n: started, c: certs })),
    focus ? row(t("coach_plan"), t("coach_plan_v", { role: roleTitle(focus), n: ticked })) : null,
    row(t("coach_where"), countryName(where())),
    h("p", { class: "tiny muted", style: { marginTop: "12px" } }, t(llm.mode === "llm" ? "coach_ai_gpu" : llm.mode === "backup" ? "coach_ai_backup" : "coach_ai_off")),
    h("p", { class: "tiny muted" }, t("coach_privacy")),
    h("a", { class: "small", href: "#/start?step=2" }, t("edit")));
}

function needProfile() {
  return h("div", { class: "container" }, h("section", { class: "wizard", style: { textAlign: "center" } },
    h("h1", {}, t("coach_need_title")), h("p", { class: "sub" }, t("coach_need_sub")),
    h("div", { class: "wizard-actions", style: { justifyContent: "center" } },
      h("a", { class: "btn btn-primary btn-lg", href: "#/start?step=1" }, t("hero_start")),
      h("a", { class: "btn btn-secondary btn-lg", href: "#/coach?persona=aisyah" }, t("coach_try_example")))));
}

export function viewCoach() {
  if (!hasProfile()) return needProfile();
  const c = coach();
  if (c.pending && !c.busy) {
    const q = c.pending;
    c.pending = null;
    setTimeout(() => send(q));
  }
  const log = h("div", { class: "chat-log coach-log", "aria-live": "polite" },
    h("div", { class: "msg assistant" }, h("p", {}, t("coach_hello"))),
    c.messages.map(message),
    c.busy ? h("div", { class: "msg assistant note" }, h("p", {}, t("coach_thinking"))) : null);
  setTimeout(() => { log.scrollTop = log.scrollHeight; });
  const box = h("textarea", { name: "q", rows: 2, maxlength: 600, placeholder: t("coach_ph"), "aria-label": t("coach_ph"),
    onkeydown: (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); e.currentTarget.form.requestSubmit(); } } });
  return h("div", {},
    h("section", { class: "page-head" }, h("div", { class: "container" },
      h("h1", {}, t("coach_title")), h("p", {}, t("coach_sub")))),
    h("section", { class: "band", style: { paddingTop: "24px" } }, h("div", { class: "container coach-grid" },
      h("section", { class: "card coach-chat" },
        h("div", { class: "ai-head" }, icon("sparkles"), h("h2", {}, t("nav_coach")), h("span", { class: "spacer" }),
          c.messages.length ? h("button", { type: "button", class: "btn btn-secondary btn-sm", disabled: c.busy,
            onclick: () => { c.messages = []; save(); rerender(); } }, t("coach_new")) : null),
        log,
        c.messages.length ? null : h("div", { class: "chips", style: { marginTop: "12px" } },
          SUGGESTED.map((k) => h("button", { type: "button", class: "chip-sm", onclick: () => send(t(k)) }, t(k)))),
        h("form", { class: "chat-form coach-form", onsubmit: (e) => { e.preventDefault(); send(box.value); box.value = ""; } },
          box, h("button", { type: "submit", class: "btn btn-primary", disabled: c.busy }, t("chat_send")))),
      seesPanel())));
}

// The results page's entry to the coach: three questions that open it already asked.
export function coachEntry() {
  return h("section", { class: "card career-chat" },
    h("div", { class: "ai-head" }, icon("sparkles"), h("h2", {}, t("coach_entry_t"))),
    h("p", { class: "small muted" }, t("coach_entry_d")),
    h("div", { class: "chips", style: { marginTop: "12px" } },
      ["chat_q_first", "chat_q_fastest", "coach_q_week"].map((k) => h("button", { type: "button", class: "chip-sm", onclick: () => askCoach(t(k)) }, t(k))),
      h("a", { class: "btn btn-primary btn-sm", href: "#/coach" }, t("coach_open"))));
}
