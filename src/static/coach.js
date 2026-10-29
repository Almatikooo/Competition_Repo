// AI chat (the career coach, #/chat): a chat that knows the person's journey. Their browser sends the profile, course progress, certificates
// and ticked plan steps with each question; the server builds the facts, the model answers from them only (every
// number is checked) and may add up to three links to Path.AI pages it was offered. The conversation stays here.
// The page is laid out like a modern chat app: a centred conversation column, plain assistant turns, the person's
// turns in bubbles, and a rounded composer that stays at the bottom of the screen.
import { h } from "./charts.js";
import { state, store, t, api, skillName, skillShort, roleTitle, hasProfile, icon, rerender, go, toast, bump, DEFAULT_LANGUAGES } from "./core.js";
import { countryName } from "./next.js";

const KEEP = 30;               // messages kept in this browser
const SEND = 12;               // messages sent with a question (the server lets the model see the latest few)
const SUGGESTED = ["coach_q_week", "chat_q_first", "chat_q_fastest", "chat_q_jobs", "coach_q_compare", "coach_q_cv", "coach_q_interview"];

const coach = () => (state.coach ||= { messages: store.get("coach", []), busy: false, pending: null, draft: "", drawer: false, seen: -1, focus: false });
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
  bump("chat");                                            // for the achievements
  c.busy = true;
  c.draft = "";
  c.focus = true;
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
  c.focus = true;
  save();
  rerender();
}

// Opens the coach with a question already asked (from the results page).
export function askCoach(question) {
  coach().pending = question;
  go("#/chat");
}

function linkChip(l) {
  const a = (href, label, ic, external) => h("a", { class: "coach-chip", href, ...(external ? { target: "_blank", rel: "noopener" } : {}) },
    icon(ic), h("span", {}, label));
  if (l.kind === "plan") return a(`#/plan/${l.id}`, t("coach_link_plan", { role: roleTitle(l.id) }), "route");
  if (l.kind === "course") return a(`#/learn/${l.id}`, t("coach_link_course", { skill: skillName(l.id) }), "book");
  if (l.kind === "jobs") return a(`#/next?mode=work&country=${l.country}`, t("coach_link_jobs", { country: countryName(l.country) }), "briefcase");
  if (l.kind === "job") return a(l.url, `${l.title} · ${l.company}`, "briefcase", true);
  if (l.kind === "learn") return a("#/learn", t("coach_link_learn"), "book");
  return null;
}

// Plain sentences, "- " lists and **bold**: built as DOM nodes, so nothing the model writes is ever treated as HTML.
function inline(text) {
  return text.split(/(\*\*[^*]+\*\*)/).filter(Boolean).map((part) => (/^\*\*[^*]+\*\*$/.test(part) ? h("strong", {}, part.slice(2, -2)) : part));
}

function answerText(text) {
  const blocks = [];
  let list = null;
  for (const line of text.split("\n").map((x) => x.trim()).filter(Boolean)) {
    if (/^[-•*]\s+/.test(line)) {
      if (!list) blocks.push((list = h("ul", {})));
      list.append(h("li", {}, inline(line.replace(/^[-•*]\s+/, ""))));
    } else {
      list = null;
      blocks.push(h("p", {}, inline(line)));
    }
  }
  return blocks;
}

function copyButton(text) {
  return h("button", { type: "button", class: "coach-icon-btn", title: t("coach_copy"), "aria-label": t("coach_copy"),
    onclick: async () => { try { await navigator.clipboard.writeText(text); toast(t("coach_copied")); } catch { /* not allowed here */ } } },
  icon("copy"));
}

function turn(m) {
  if (m.role === "user") return h("div", { class: "coach-turn user" }, h("div", { class: "coach-bubble" }, m.content));
  if (m.note) return h("div", { class: "coach-turn assistant note" }, icon("shield"), h("p", {}, m.content));
  return h("div", { class: "coach-turn assistant" },
    h("div", { class: "coach-answer" }, answerText(m.content)),
    m.links?.length ? h("div", { class: "coach-chips" }, m.links.map(linkChip)) : null,
    h("div", { class: "coach-actions" }, copyButton(m.content)));
}

function personName() {
  const o = state.origin;
  return o?.type === "persona" ? state.personas.find((p) => p.id === o.id)?.name || "" : "";
}

function status() {
  const mode = state.meta.llm?.mode;
  const [cls, key] = mode === "llm" ? ["on", "coach_status_gpu"] : mode === "backup" ? ["backup", "coach_status_backup"] : ["off", "coach_status_off"];
  return h("span", { class: `coach-status ${cls}` }, h("i", {}), t(key));
}

function topBar(c) {
  return h("div", { class: "coach-top" },
    h("div", { class: "coach-top-title" }, icon("sparkles"), h("b", {}, t("nav_coach")), status()),
    h("div", { class: "coach-top-actions" },
      h("button", { type: "button", class: "coach-ghost", "aria-expanded": String(c.drawer), onclick: () => { c.drawer = !c.drawer; rerender(); } },
        icon("eye"), h("span", {}, t("coach_see_btn"))),
      h("button", { type: "button", class: "coach-ghost", disabled: !c.messages.length || c.busy, title: t("coach_new"),
        onclick: () => { c.messages = []; c.draft = ""; c.focus = true; save(); rerender(); } }, icon("pen"), h("span", {}, t("coach_new")))));
}

function composer(c) {
  const box = h("textarea", { rows: 1, maxlength: 600, placeholder: t("coach_ph"), "aria-label": t("coach_ph"), class: "coach-input",
    oninput: (e) => { c.draft = e.currentTarget.value; grow(e.currentTarget); sendBtn.disabled = c.busy || !c.draft.trim(); },
    onkeydown: (e) => { if (e.key === "Enter" && !e.shiftKey && !e.isComposing) { e.preventDefault(); send(c.draft); } } });
  box.value = c.draft;
  const sendBtn = h("button", { type: "submit", class: "coach-send", disabled: c.busy || !c.draft.trim(), "aria-label": t("chat_send"), title: t("chat_send") },
    icon("send"));
  return h("form", { class: "coach-composer", onsubmit: (e) => { e.preventDefault(); send(c.draft); } }, box, sendBtn);
}

function grow(box) {
  box.style.height = "auto";
  box.style.height = `${Math.min(box.scrollHeight, 200)}px`;
}

function drawer(c) {
  const p = state.profile;
  const strongest = Object.entries(p.skills).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([id]) => skillShort(id));
  const top = (state.matches?.roles || []).slice(0, 3);
  const started = Object.values(state.learned || {}).filter((x) => (x.done || []).length).length;
  const certs = Object.keys(state.certs || {}).length;
  const focus = store.get("focusRole", null);
  const ticked = focus ? Object.values(state.progress?.[focus] || {}).filter(Boolean).length : 0;
  const mode = state.meta.llm?.mode;
  const row = (label, value) => h("div", { class: "coach-fact" }, h("span", {}, label), h("b", {}, value));
  const close = () => { c.drawer = false; rerender(); };
  return [h("div", { class: "coach-scrim", onclick: close }),
    h("aside", { class: "coach-drawer", "aria-label": t("coach_sees") },
      h("div", { class: "coach-drawer-head" }, h("h2", {}, t("coach_sees")),
        h("button", { type: "button", class: "coach-icon-btn", "aria-label": t("coach_close"), onclick: close }, icon("close"))),
      row(t("coach_job"), p.current_role ? roleTitle(p.current_role) : "–"),
      row(t("coach_skills"), strongest.join(", ") || "–"),
      top.length ? row(t("coach_top"), top.map((r) => `${roleTitle(r.id)} · ${r.fit}%`).join("\n")) : null,
      row(t("coach_learning"), t("coach_learning_v", { n: started, c: certs })),
      focus ? row(t("coach_plan"), t("coach_plan_v", { role: roleTitle(focus), n: ticked })) : null,
      row(t("coach_where"), countryName(where())),
      h("p", { class: "coach-drawer-note" }, t(mode === "llm" ? "coach_ai_gpu" : mode === "backup" ? "coach_ai_backup" : "coach_ai_off")),
      h("p", { class: "coach-drawer-note" }, t("coach_privacy")),
      h("a", { class: "btn btn-secondary btn-sm", href: "#/start?step=2" }, t("edit")))];
}

function needProfile() {
  return h("div", { class: "coach-app coach-empty" }, h("div", { class: "coach-col" }, h("div", { class: "coach-hero" },
    h("div", { class: "coach-mark" }, icon("sparkles")),
    h("h1", {}, t("coach_need_title")), h("p", {}, t("coach_need_sub")),
    h("div", { class: "coach-hero-actions" },
      h("a", { class: "btn btn-primary", href: "#/start?step=1" }, t("hero_start")),
      h("a", { class: "btn btn-secondary", href: "#/chat?persona=aisyah" }, t("coach_try_example"))))));
}

export function viewCoach() {
  if (!hasProfile()) return needProfile();
  const c = coach();
  if (c.pending && !c.busy) {
    const q = c.pending;
    c.pending = null;
    setTimeout(() => send(q));
  }
  const empty = !c.messages.length && !c.busy;
  const name = personName();
  const fine = h("p", { class: "coach-fine" }, t("coach_fine"));
  const page = h("div", { class: `coach-app${empty ? " coach-empty" : ""}`, "aria-label": t("coach_title") },
    topBar(c),
    empty
      ? h("div", { class: "coach-col" }, h("div", { class: "coach-hero" },
          h("div", { class: "coach-mark" }, icon("sparkles")),
          h("h1", {}, name ? t("coach_hi_name", { name }) : t("coach_hi")),
          h("p", {}, t("coach_hero_sub", { country: countryName(where()) })),
          composer(c),
          h("div", { class: "coach-suggest" }, SUGGESTED.map((k) => h("button", { type: "button", onclick: () => send(t(k)) }, t(k)))),
          fine))
      : [h("div", { class: "coach-col coach-thread", "aria-live": "polite" },
          c.messages.map(turn),
          c.busy ? h("div", { class: "coach-turn assistant" }, h("div", { class: "coach-typing", "aria-label": t("coach_thinking") }, h("i", {}), h("i", {}), h("i", {}))) : null),
        h("div", { class: "coach-dock" }, h("div", { class: "coach-col" }, composer(c), fine))],
    c.drawer ? drawer(c) : null);
  setTimeout(() => {
    const box = page.querySelector(".coach-input");
    if (box) grow(box);
    if (!empty && c.seen !== c.messages.length + (c.busy ? 1 : 0)) {
      c.seen = c.messages.length + (c.busy ? 1 : 0);
      window.scrollTo({ top: document.documentElement.scrollHeight });
    }
    if (box && (c.focus || matchMedia("(pointer: fine)").matches)) { box.focus(); c.focus = false; }
  });
  return page;
}

// The results page's entry to the coach: three questions that open it already asked.
export function coachEntry() {
  return h("section", { class: "card career-chat" },
    h("div", { class: "ai-head" }, icon("sparkles"), h("h2", {}, t("coach_entry_t"))),
    h("p", { class: "small muted" }, t("coach_entry_d")),
    h("div", { class: "chips", style: { marginTop: "12px" } },
      ["chat_q_first", "chat_q_fastest", "coach_q_week"].map((k) => h("button", { type: "button", class: "chip-sm", onclick: () => askCoach(t(k)) }, t(k))),
      h("a", { class: "btn btn-primary btn-sm", href: "#/chat" }, t("coach_open"))));
}
