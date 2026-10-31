// Rewards (#/rewards): achievements earn points (bronze 10, silver 50, gold 200; see badges.js), 1 point is worth about
// RM 1, and points pay at most half the price of a gift: the rest is paid in money. Thirty gifts, from a sticker pack
// to a MacBook, each with a product photo on white (the merch is our own; the others are openly licensed and credited
// at the bottom of the page). A claim is a demo: it keeps a code and the points it used, but no order is placed and
// nothing is charged.
import { h } from "./charts.js";
import { state, store, t, account, icon, rerender, keepOpen } from "./core.js";
import { POINTS, earnedPoints, spentPoints, pointsBalance, fmtPoints, renderPoints, openBadge } from "./badges.js";
import { signInButtons, canSignIn } from "./account.js";
import { PHOTOS } from "./reward-photos.js";

// id, group, icon and price in ringgit (indicative), cheapest first
const G = (id, cat, ic, price) => ({ id, cat, icon: ic, price });
export const CATALOG = [
  G("stickers", "merch", "sticker", 10),
  G("coffee", "life", "coffee", 15),
  G("bubble_tea", "life", "cup", 20),
  G("notebook", "merch", "notebook", 25),
  G("mug", "merch", "mug", 35),
  G("cable", "tech", "plug", 39),
  G("ebook", "learn", "book", 49),
  G("food", "life", "bag", 50),
  G("tshirt", "merch", "shirt", 59),
  G("mouse", "tech", "mouse", 69),
  G("powerbank", "tech", "battery", 89),
  G("ewallet", "life", "wallet", 100),
  G("stand", "tech", "stand", 120),
  G("webcam", "tech", "camera", 149),
  G("backpack", "merch", "backpack", 169),
  G("speaker", "tech", "speaker", 199),
  G("course_pass", "learn", "bookOpen", 249),
  G("keyboard", "tech", "keyboard", 299),
  G("earbuds", "tech", "earbuds", 349),
  G("exam", "learn", "award", 450),
  G("ereader", "tech", "ereader", 599),
  G("monitor", "tech", "monitor", 699),
  G("smartwatch", "tech", "watch", 899),
  G("headphones", "tech", "headset", 1199),
  G("bootcamp", "learn", "grad", 1500),
  G("tablet", "tech", "tablet", 1699),
  G("phone", "tech", "phone", 2199),
  G("ipad_air", "tech", "tablet", 2799),
  G("laptop", "tech", "laptop", 3299),
  G("macbook", "tech", "laptop", 4999),
];
const CATS = ["all", "learn", "tech", "life", "merch"];
export const MAX_SHARE = 0.5;                                     // points pay at most half the price
export const maxPoints = (price) => Math.floor(price * MAX_SHARE);
const rm = (n) => t("rw_price", { n: fmtPoints(n) });
const giftName = (g) => t(`rw_i_${g.id}`);

// Every gift has its photo, /static/rewards/<id>.jpg.
const photo = (g, lazy = true) => h("img", { src: `/static/rewards/${g.id}.jpg`, alt: "", loading: lazy ? "lazy" : "eager", decoding: "async" });

function tile(g, top = false) {
  return h("div", { class: `rw-tile rw-${top ? "top" : g.cat} photo` }, photo(g, !top), h("span", { class: "rw-cat" }, t(`rw_cat_${g.cat}`)));
}
const mini = (g) => h("span", { class: `rw-mini rw-${g.cat} photo` }, photo(g, false));

// Who took each photo, under which licence, and where the original is.
function credits() {
  return h("details", { class: "rw-credits small", ...keepOpen("rwCredits") }, h("summary", {}, t("rw_credits")),
    h("p", { class: "muted" }, t("rw_credits_note")),
    h("ul", {}, CATALOG.filter((g) => PHOTOS[g.id]).map((g) => {
      const p = PHOTOS[g.id];
      return h("li", {}, h("b", {}, giftName(g)), ": ", h("a", { href: p.source, target: "_blank", rel: "noopener" }, p.title), ` · ${p.author} · `,
        p.license_url ? h("a", { href: p.license_url, target: "_blank", rel: "noopener" }, p.license) : p.license);
    })));
}

// How much of the most points this gift takes the person already has, and what is left to pay.
function reach(g, balance) {
  const most = maxPoints(g.price), use = Math.min(balance, most);
  return { most, use, pct: Math.round((use / most) * 100), cash: g.price - use };
}

function card(g, balance) {
  const r = reach(g, balance);
  return h("article", { class: `rw-card${r.use === r.most ? " full" : ""}` },
    tile(g),
    h("div", { class: "rw-body" },
      h("h3", {}, giftName(g)),
      h("p", { class: "small muted" }, t(`rw_d_${g.id}`)),
      h("div", { class: "rw-price" }, h("b", {}, rm(g.price)), h("span", { class: "small muted" }, t("rw_up_to", { n: fmtPoints(r.most) }))),
      h("div", { class: "pbar", role: "img", "aria-label": `${r.pct}%` }, h("span", { style: { width: `${r.pct}%` } })),
      h("p", { class: "small rw-pay" }, r.use ? t("rw_you_pay", { n: fmtPoints(r.cash) }) : t("rw_need_any")),
      h("button", { type: "button", class: "btn btn-primary btn-sm btn-block", onclick: (e) => openRedeem(g, e.currentTarget) }, t("rw_redeem"))));
}

function featured(g, balance) {
  const r = reach(g, balance);
  return h("section", { class: "card rw-featured" },
    tile(g, true),
    h("div", { class: "rw-featured-body" },
      h("p", { class: "kicker" }, icon("crown"), t("rw_top")),
      h("h2", {}, giftName(g)),
      h("p", { class: "muted" }, t(`rw_d_${g.id}`)),
      h("p", { class: "rw-featured-price" }, h("b", {}, rm(g.price)), h("span", { class: "muted" }, ` · ${t("rw_up_to", { n: fmtPoints(r.most) })}`)),
      h("div", { class: "progress" }, h("span", { style: { width: `${r.pct}%` } })),
      h("p", { class: "small muted" }, t("rw_top_prog", { have: fmtPoints(r.use), max: fmtPoints(r.most) })),
      h("button", { type: "button", class: "btn btn-primary", onclick: (e) => openRedeem(g, e.currentTarget) }, t("rw_redeem"))));
}

function mine() {
  const claims = [...(state.rewards || [])].reverse();
  if (!claims.length) return null;
  const by = Object.fromEntries(CATALOG.map((g) => [g.id, g]));
  return h("section", { class: "card rw-mine" }, h("h2", {}, t("rw_mine")),
    claims.map((c) => h("div", { class: "rw-claim" },
      by[c.item] ? mini(by[c.item]) : null,
      h("div", {}, h("b", {}, by[c.item] ? giftName(by[c.item]) : c.item),
        h("p", { class: "small muted" }, t("rw_mine_row", { date: new Date(c.at).toLocaleDateString("en-MY", { day: "numeric", month: "short", year: "numeric" }),
          points: fmtPoints(c.points), cash: fmtPoints(c.cash) }))),
      h("code", { class: "rw-code" }, c.id))));
}

export function viewRewards() {
  const balance = pointsBalance(), f = state.rewardsUi;
  const shown = CATALOG.filter((g) => (f.cat === "all" || g.cat === f.cat) && (!f.reach || balance >= maxPoints(g.price)));
  const count = (cat) => CATALOG.filter((g) => cat === "all" || g.cat === cat).length;
  const set = (patch) => { Object.assign(f, patch); rerender(); };
  return h("div", {},
    h("section", { class: "page-head" }, h("div", { class: "container rw-hero" },
      h("div", { class: "rw-hero-text" },
        h("h1", {}, t("rw_title")), h("p", {}, t("rw_sub")),
        h("ol", { class: "rw-how" },
          h("li", {}, t("rw_how_1", { b: POINTS[1], s: POINTS[2], g: POINTS[3] })),
          h("li", {}, t("rw_how_2")),
          h("li", {}, t("rw_how_3")))),
      h("div", { class: "rw-balance" },
        h("p", { class: "rw-balance-k" }, t("rw_balance")),
        h("p", { class: "rw-balance-v" }, icon("gift"), h("b", {}, fmtPoints(balance))),
        h("p", { class: "rw-balance-rm" }, t("rw_worth", { n: fmtPoints(balance) })),
        h("p", { class: "small rw-balance-split" }, `${t("rw_earned", { n: fmtPoints(earnedPoints()) })} · ${t("rw_spent", { n: fmtPoints(spentPoints()) })}`),
        h("a", { class: "btn btn-sm rw-balance-btn", href: "#/me", onclick: (e) => { e.preventDefault(); openBadge(); } }, t("rw_see_ach"), " →")))),
    h("section", { class: "band", style: { paddingTop: "28px" } }, h("div", { class: "container rw-page" },
      featured(CATALOG[CATALOG.length - 1], balance),
      h("div", { class: "rw-filters" },
        h("div", { class: "seg-tabs", role: "group", "aria-label": t("rw_title") }, CATS.map((cat) =>
          h("button", { type: "button", class: f.cat === cat ? "on" : "", "aria-pressed": String(f.cat === cat), onclick: () => set({ cat }) },
            t(cat === "all" ? "rw_all" : `rw_cat_${cat}`), h("span", { class: "n" }, String(count(cat)))))),
        h("button", { type: "button", class: `chip${f.reach ? " on" : ""}`, "aria-pressed": String(f.reach), onclick: () => set({ reach: !f.reach }) },
          icon("check"), t("rw_reach"))),
      shown.length ? h("div", { class: "rw-grid" }, shown.map((g) => card(g, balance))) : h("p", { class: "muted rw-empty" }, t("rw_empty")),
      mine(),
      h("p", { class: "small muted rw-note" }, `${t("rw_indicative")} ${t("rw_demo")}`),
      credits())));
}

// ---------------------------------------------------------------- claiming a gift
const code = () => {
  const abc = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789", bytes = crypto.getRandomValues(new Uint8Array(8));
  const s = [...bytes].map((b) => abc[b % abc.length]).join("");
  return `PAI-${s.slice(0, 4)}-${s.slice(4)}`;
};

function openRedeem(g, opener) {
  const most = maxPoints(g.price);
  let use = Math.min(pointsBalance(), most), done = null, dlg;
  const close = () => dlg.close();
  const body = h("div", { class: "rw-dlg-body" });
  const line = (k, v, cls = "") => h("div", { class: `rw-line ${cls}` }, h("span", {}, k), h("b", {}, v));
  const head = () => h("div", { class: "rw-dlg-gift" }, mini(g),
    h("div", {}, h("h2", { id: "rw-dlg-title" }, giftName(g)), h("p", { class: "muted" }, rm(g.price))));

  function claim() {
    use = Math.min(use, most, pointsBalance());
    if (use < 1) return;
    done = { id: code(), item: g.id, price: g.price, points: use, cash: g.price - use, at: new Date().toISOString() };
    state.rewards = [...(state.rewards || []), done];
    store.set("rewards", state.rewards);
    renderPoints();
    draw();
  }

  function content() {
    if (done) {
      return [h("div", { class: "rw-done" }, h("span", { class: "rw-done-ico" }, icon("gift")),
        h("h2", { id: "rw-dlg-title" }, t("rw_done_t")), h("p", {}, giftName(g)),
        h("p", { class: "small muted" }, t("rw_done_code")), h("code", { class: "rw-code big" }, done.id),
        h("div", { class: "rw-lines" }, line(t("rw_line_points"), t("rw_points", { n: fmtPoints(done.points) })), line(t("rw_line_cash"), rm(done.cash), "total")),
        h("p", { class: "small" }, t("rw_done_d", { cash: fmtPoints(done.cash) })),
        h("p", { class: "small muted" }, t("rw_demo")),
        h("button", { type: "button", class: "btn btn-primary btn-block", onclick: close }, t("close")))];
    }
    if (!account.user) {
      return [head(), h("p", {}, t("rw_signin")),
        canSignIn() ? h("div", { class: "acc-buttons" }, signInButtons("#/rewards")) : null,
        h("button", { type: "button", class: "btn btn-secondary btn-block", onclick: close }, t("acc_cancel"))];
    }
    const balance = pointsBalance(), max = Math.min(balance, most);
    if (max < 1) {
      return [head(), h("p", {}, t("rw_no_points")),
        h("div", { class: "row", style: { gap: "8px" } },
          h("button", { type: "button", class: "btn btn-primary", onclick: () => { close(); openBadge(); } }, t("rw_see_ach"), " →"),
          h("button", { type: "button", class: "btn btn-secondary", onclick: close }, t("acc_cancel")))];
    }
    const pointsOut = h("b", {}, `− ${rm(use)}`), cashOut = h("b", {}, rm(g.price - use)), confirm = h("button", { type: "button", class: "btn btn-primary btn-block", onclick: claim }, t("rw_confirm", { n: fmtPoints(use) }));
    const slider = h("input", { type: "range", min: 1, max, step: 1, value: use, "aria-label": t("rw_use"),
      oninput: (e) => { use = Number(e.target.value); pointsOut.textContent = `− ${rm(use)}`; cashOut.textContent = rm(g.price - use); confirm.textContent = t("rw_confirm", { n: fmtPoints(use) }); } });
    return [head(),
      h("p", { class: "small muted" }, t("rw_rule", { n: fmtPoints(most) })),
      h("label", { class: "rw-use" }, h("span", {}, t("rw_use")), slider, h("span", { class: "small muted" }, t("rw_have", { n: fmtPoints(balance) }))),
      h("div", { class: "rw-lines" }, line(t("rw_line_price"), rm(g.price)),
        h("div", { class: "rw-line" }, h("span", {}, t("rw_line_points")), pointsOut),
        h("div", { class: "rw-line total" }, h("span", {}, t("rw_line_cash")), cashOut)),
      confirm,
      h("button", { type: "button", class: "btn btn-link btn-block", onclick: close }, t("acc_cancel"))];
  }
  function draw() { body.replaceChildren(...content().filter(Boolean)); }

  dlg = h("dialog", { class: "rw-dialog", "aria-labelledby": "rw-dlg-title", onclick: (e) => { if (e.target === dlg) close(); },
    onclose: () => { dlg.remove(); if (done) rerender(); else if (opener?.isConnected) opener.focus(); } },
  h("button", { type: "button", class: "rw-dlg-x", "aria-label": t("close"), onclick: close }, icon("close")), body);
  draw();
  document.body.append(dlg);
  dlg.showModal();
}
