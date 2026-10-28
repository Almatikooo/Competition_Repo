// My profile (#/me): who the person is on Path.AI and where they stand. It shows their account, experience and
// languages (editable here), skills, best roles and plan, courses and certificates, and where they look for work or
// study. A guest sees the same from this tab, with a nudge to sign in.
import { h } from "./charts.js";
import { state, store, t, account, signOut, deleteAccount, hasProfile, roleTitle, skillName, icon, rerender, sdgBadge, loc, monthLabel, toast } from "./core.js";
import { aboutYou, countryName } from "./next.js";
import { signInButtons, canSignIn, avatar } from "./account.js";

const card = (title, ...body) => h("section", { class: "card me-card" }, h("h2", {}, title), ...body);
const row = (label, value) => h("div", { class: "me-row" }, h("span", { class: "k" }, label), h("span", { class: "v" }, value));
const link = (href, label) => h("a", { class: "me-link", href }, label, " →");

function identity() {
  const u = account.user;
  if (!u) {
    return h("section", { class: "card me-id" }, h("span", { class: "me-avatar guest" }, icon("user")),
      h("div", { class: "me-id-text" }, h("h2", {}, t("me_guest")), h("p", { class: "muted" }, t("acc_guest_note")),
        canSignIn() ? h("div", { class: "acc-buttons me-signin" }, signInButtons()) : null));
  }
  const provider = { google: "Google", github: "GitHub" }[u.provider] || u.provider;
  return h("section", { class: "card me-id" }, avatar(u, "me-avatar"),
    h("div", { class: "me-id-text" }, h("h2", {}, u.name || u.email),
      u.name && u.email ? h("p", { class: "muted" }, u.email) : null,
      h("p", { class: "small muted" }, [provider ? t("me_with", { provider }) : null, u.since ? t("me_since", { date: monthLabel(u.since.slice(0, 7)) }) : null]
        .filter(Boolean).join(" · "))));
}

function about() {
  const p = state.profile;
  const tiles = (state.meta.interest_tiles || []).filter((x) => (state.tiles || []).includes(x.id));
  return card(t("me_about"),
    row(t("me_job"), p.current_role ? roleTitle(p.current_role) : "–"),
    row(t("me_hours"), t("me_hours_v", { n: p.hours_per_week || 0 })),
    aboutYou(),
    tiles.length ? row(t("me_interests"), tiles.map((x) => loc(x.label)).join(", ")) : null,
    p.sdg_priorities?.length ? h("div", { class: "me-row" }, h("span", { class: "k" }, t("me_goals")),
      h("span", { class: "v sdg-strip" }, p.sdg_priorities.map((g) => sdgBadge(g)))) : null,
    link("#/start?step=1", t("me_edit")));
}

function skills() {
  const p = state.profile;
  const by = [3, 2, 1].map((lvl) => [lvl, Object.entries(p.skills).filter(([, l]) => l === lvl).map(([id]) => id)]).filter(([, ids]) => ids.length);
  return card(t("me_skills"),
    by.length ? by.map(([lvl, ids]) => h("div", { class: "me-skill-group" }, h("p", { class: "k" }, t(`me_lvl_${lvl}`)),
      h("div", { class: "chips" }, ids.map((id) => h("span", { class: "chip-sm static" }, skillName(id)))))) : h("p", { class: "muted" }, t("me_no_skills")),
    link("#/start?step=2", t("me_edit")));
}

function path() {
  const top = (state.matches?.roles || []).slice(0, 3);
  const focus = store.get("focusRole", null);
  const ticked = focus ? Object.values(state.progress?.[focus] || {}).filter(Boolean).length : 0;
  return card(t("me_path"),
    top.length ? h("div", {}, h("p", { class: "k" }, t("me_best")),
      h("ol", { class: "me-roles" }, top.map((r) => h("li", {}, h("a", { href: `#/plan/${r.id}` }, roleTitle(r.id)), h("span", { class: "muted" }, ` · ${r.fit}%`))))) : null,
    focus ? row(t("me_plan"), h("span", {}, h("a", { href: `#/plan/${focus}` }, roleTitle(focus)), h("span", { class: "muted" }, ` · ${t("me_plan_v", { n: ticked })}`))) : null,
    link("#/results", t("me_open")));
}

function learning() {
  const courses = Object.fromEntries((state.courses || []).map((c) => [c.skill, c]));
  const started = Object.entries(state.learned || {}).filter(([, x]) => (x.done || []).length);
  const certs = Object.entries(state.certs || {});
  return card(t("me_learning"),
    started.length ? started.map(([sid, x]) => {
      const total = courses[sid]?.lessons || x.done.length;
      const pct = Math.round((Math.min(x.done.length, total) / total) * 100);
      return h("a", { class: "me-course", href: `#/learn/${sid}` }, h("span", {}, skillName(sid)),
        h("span", { class: "me-bar", role: "img", "aria-label": `${pct}%` }, h("span", { style: { width: `${pct}%` } })),
        h("span", { class: "small muted" }, t("me_lessons", { d: Math.min(x.done.length, total), n: total })));
    }) : h("p", { class: "muted" }, t("me_no_courses")),
    certs.length ? h("div", { class: "me-certs" }, h("p", { class: "k" }, t("me_certs")),
      certs.map(([sid, token]) => h("a", { class: "chip-sm cert", href: `#/certificate/${token}` }, icon("award"), skillName(sid)))) : null,
    link("#/learn", t("me_browse")));
}

function elsewhere() {
  const n = state.next || {};
  const chat = store.get("coach", []).length;
  return card(t("me_more"),
    row(t("me_where"), n.mode && n.country ? h("a", { href: "#/next" }, t("me_where_v", { mode: t(n.mode === "study" ? "me_study" : "me_work"), country: countryName(n.country) }))
      : h("a", { href: "#/next" }, t("me_where_none"))),
    row(t("nav_coach"), h("a", { href: "#/chat" }, chat ? t("me_chat_v", { n: chat }) : t("me_chat_none"))));
}

function accountCard() {
  const fail = (e) => toast(String(e.message || e));
  return card(t("me_account"),
    state.meDeleting
      ? [h("p", {}, t("acc_delete_sure")), h("div", { class: "row", style: { gap: "8px" } },
          h("button", { type: "button", class: "btn btn-sm acc-danger", onclick: () => deleteAccount().catch(fail) }, t("acc_delete_yes")),
          h("button", { type: "button", class: "btn btn-secondary btn-sm", onclick: () => { state.meDeleting = false; rerender(); } }, t("acc_cancel")))]
      : h("div", { class: "row", style: { gap: "10px", flexWrap: "wrap" } },
          h("button", { type: "button", class: "btn btn-secondary btn-sm", onclick: () => signOut().catch(fail) }, t("acc_signout")),
          h("button", { type: "button", class: "acc-delete", onclick: () => { state.meDeleting = true; rerender(); } }, t("acc_delete"))));
}

export function viewProfile() {
  const signedIn = !!account.user;
  return h("div", {},
    h("section", { class: "page-head" }, h("div", { class: "container" },
      h("h1", {}, t("me_title")), h("p", {}, t(signedIn ? "me_sub_saved" : "me_sub_guest")))),
    h("section", { class: "band", style: { paddingTop: "28px" } }, h("div", { class: "container me-grid" },
      identity(),
      hasProfile() ? [about(), skills(), path(), learning(), elsewhere()]
        : h("section", { class: "card me-card me-empty" }, h("p", {}, t("me_no_profile")), h("a", { class: "btn btn-primary", href: "#/start?step=1" }, t("hero_start"))),
      signedIn ? accountCard() : null)));
}
