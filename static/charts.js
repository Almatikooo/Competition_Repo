// Small, dependency-free chart kit. All text goes in via textContent (never innerHTML).
const SVG_NS = "http://www.w3.org/2000/svg";

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  setAttrs(el, attrs);
  append(el, children);
  return el;
}

export function s(tag, attrs = {}, ...children) {
  const el = document.createElementNS(SVG_NS, tag);
  setAttrs(el, attrs);
  append(el, children);
  return el;
}

function setAttrs(el, attrs) {
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") el.setAttribute("class", v);
    else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
    else if (k === "style" && typeof v === "object") { for (const [p, val] of Object.entries(v)) { if (p.startsWith("--")) el.style.setProperty(p, val); else el.style[p] = val; } }
    else el.setAttribute(k, v === true ? "" : v);
  }
}

function append(el, children) {
  for (const c of children.flat(Infinity)) {
    if (c == null || c === false) continue;
    el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
}

// ---------------------------------------------------------------- tooltip
const tip = () => document.getElementById("tooltip");

export function showTip(evt, build) {
  const el = tip();
  el.replaceChildren(build());
  el.style.display = "block";
  moveTip(evt);
}

export function moveTip(evt) {
  const el = tip();
  let x, y;
  if (evt && "clientX" in evt && evt.clientX) {
    x = evt.clientX + 14; y = evt.clientY + 14;
  } else if (evt && evt.target && evt.target.getBoundingClientRect) {
    const r = evt.target.getBoundingClientRect();
    x = r.right + 8; y = r.top;
  } else return;
  const w = el.offsetWidth, hgt = el.offsetHeight;
  if (x + w > window.innerWidth - 8) x = Math.max(8, x - w - 28);
  if (y + hgt > window.innerHeight - 8) y = Math.max(8, window.innerHeight - hgt - 8);
  el.style.left = `${x}px`;
  el.style.top = `${y}px`;
}

export function hideTip() { tip().style.display = "none"; }

export const fmtPct = (v) => (v == null ? "–" : `${v > 0 ? "+" : ""}${v.toFixed(Math.abs(v) < 10 ? 1 : 0)}%`);

export function trendSpan(v, suffix = "") {
  const cls = v > 1 ? "up" : v < -1 ? "down" : "flat";
  const arrow = v > 1 ? "▲" : v < -1 ? "▼" : "■";
  return h("span", { class: `trend ${cls}` }, h("span", { "aria-hidden": "true" }, arrow), fmtPct(v) + suffix);
}

// ---------------------------------------------------------------- Future Skills Radar
const RINGS = ["surging", "rising", "stable", "declining"];
const QUADS = ["ai_data", "digital", "green", "human"];

export function radar({ skills, categories, names, shorts, mine, t, lang, onSelect }) {
  const size = 680, c = size / 2, R = 300;
  const outer = [0.3, 0.54, 0.77, 1].map((f) => f * R);
  const inner = [0, ...outer.slice(0, 3)];
  const svg = s("svg", { viewBox: `0 0 ${size} ${size}`, role: "img", "aria-label": t("radar_title") });
  outer.slice().reverse().forEach((r, i) => svg.append(s("circle", { cx: c, cy: c, r, class: `radar-ring ${i === 3 ? "radar-ring-fill-0" : ""}` })));
  svg.append(s("line", { x1: c - R, y1: c, x2: c + R, y2: c, class: "radar-axis" }));
  svg.append(s("line", { x1: c, y1: c - R, x2: c, y2: c + R, class: "radar-axis" }));
  const ringLabels = RINGS.map((ring, i) => s("text", { x: c, y: c + (i ? (inner[i] + outer[i]) / 2 : outer[0] * 0.62) + 4,
    "text-anchor": "middle", class: "radar-ring-label" }, t(`ring_${ring}`)));
  const quadAngle = { ai_data: -90, digital: 0, green: 90, human: 180 };
  const quadLabelPos = { ai_data: [c + R * 0.98, 28, "end"], digital: [c + R * 0.98, size - 14, "end"], green: [c - R * 0.98, size - 14, "start"], human: [c - R * 0.98, 28, "start"] };
  QUADS.forEach((q) => {
    const [x, y, anchor] = quadLabelPos[q];
    svg.append(s("text", { x, y, "text-anchor": anchor, class: "radar-quad" }, categories[q][lang] || categories[q].en));
  });

  const labelled = new Set([...mine]);
  const sorted = skills.slice().sort((a, b) => b.pct - a.pct);
  sorted.slice(0, 3).forEach((x) => labelled.add(x.id));
  sorted.slice(-3).forEach((x) => labelled.add(x.id));

  const placed = [];
  for (const q of QUADS) {
    RINGS.forEach((ring, ri) => {
      const group = skills.filter((x) => x.category === q && x.ring === ring).sort((a, b) => b.pct - a.pct);
      const n = group.length;
      group.forEach((sk, i) => {
        const pad = 13;
        const ang = (quadAngle[q] + pad + ((i + 0.5) / n) * (90 - 2 * pad)) * (Math.PI / 180);
        const band = outer[ri] - inner[ri];
        const rr = inner[ri] + band * (n > 3 ? (i % 2 ? 0.7 : 0.32) : 0.5) + (ri === 0 ? 18 : 0) * (1 - i / Math.max(1, n));
        placed.push({ sk, x: c + Math.cos(ang) * rr, y: c + Math.sin(ang) * rr });
      });
    });
  }
  for (const { sk, x, y } of placed) {
    const isMine = mine.has(sk.id);
    const g = s("g", { class: "radar-g" });
    const hit = s("circle", { cx: x, cy: y, r: 13, class: "radar-hit", tabindex: 0, role: "button",
      "aria-label": `${names[sk.id]}: ${fmtPct(sk.pct)} ${t("per_year")}, ${t(`ring_${sk.ring}`)}` });
    const dot = s("circle", { cx: x, cy: y, r: isMine ? 7 : 5.5, class: `radar-dot ${isMine ? "mine" : ""} ${mine.size && !isMine ? "dim" : ""}`,
      fill: `var(--t-${sk.ring})` });
    const build = () => radarTip(sk, names, t);
    hit.addEventListener("pointerenter", (e) => showTip(e, build));
    hit.addEventListener("pointermove", moveTip);
    hit.addEventListener("pointerleave", hideTip);
    hit.addEventListener("focus", (e) => showTip(e, build));
    hit.addEventListener("blur", hideTip);
    hit.addEventListener("click", () => onSelect && onSelect(sk.id));
    hit.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect && onSelect(sk.id); } });
    g.append(hit, dot);
    if (labelled.has(sk.id)) {
      const right = x >= c;
      g.append(s("text", { x: x + (right ? 10 : -10), y: y + 4, "text-anchor": right ? "start" : "end", class: "radar-text" }, shortName(shorts?.[sk.id] || names[sk.id])));
    }
    svg.append(g);
  }
  svg.append(...ringLabels);  // drawn last so the halo keeps them legible over the axis
  return h("div", { class: "radar-wrap" }, svg);
}

function shortName(name) {
  const cut = name.split(/ [(&—]/)[0];
  return cut.length > 26 ? cut.slice(0, 25) + "…" : cut;
}

function radarTip(sk, names, t) {
  const comps = sk.components;
  return h("div", {},
    h("div", { class: "k" }, names[sk.id]),
    h("div", { class: "v" }, `${fmtPct(sk.pct)} ${t("per_year")}`),
    h("div", { class: "k" }, `${t("range")} ${fmtPct(sk.low)} … ${fmtPct(sk.high)} · ${t(`conf_${sk.confidence}`)}`),
    h("div", { class: "k" }, `${t("comp_market")} ${fmtPct(comps.market)} · ${t("comp_prior")} ${fmtPct(comps.prior)} · ${t("comp_ai")} ${fmtPct(comps.ai)}`));
}

// ---------------------------------------------------------------- bars
export function divergingBars(rows, { domain, format = fmtPct, labelWidth } = {}) {
  const vals = rows.flatMap((r) => [r.value, r.low ?? r.value, r.high ?? r.value]);
  const lo = Math.min(0, domain ? domain[0] : Math.min(...vals));
  const hi = Math.max(0, domain ? domain[1] : Math.max(...vals));
  const span = hi - lo || 1;
  const pos = (v) => ((Math.max(lo, Math.min(hi, v)) - lo) / span) * 100;
  const zero = pos(0);
  const wrap = h("div", { class: "bars" });
  for (const r of rows) {
    const v = r.value;
    const left = Math.min(pos(v), zero), width = Math.abs(pos(v) - zero);
    const track = h("div", { class: "bar-track" },
      h("div", { class: "zero", style: { left: `${zero}%` } }),
      h("div", { class: `bar-fill ${v < 0 ? "neg" : "pos"}`, style: { left: `${left}%`, width: `${Math.max(width, 0.6)}%` } }));
    if (r.low != null && r.high != null) {
      track.append(h("div", { class: "whisker", style: { left: `${pos(r.low)}%`, width: `${Math.max(0.5, pos(r.high) - pos(r.low))}%` } }));
    }
    const row = h("div", { class: "bar-row", tabindex: r.tip ? 0 : null, style: labelWidth ? { gridTemplateColumns: `${labelWidth} 1fr auto` } : null },
      h("div", {}, r.label), track, h("div", { class: "bar-val" }, format(v)));
    if (r.tip) {
      row.addEventListener("pointerenter", (e) => showTip(e, r.tip));
      row.addEventListener("pointermove", moveTip);
      row.addEventListener("pointerleave", hideTip);
      row.addEventListener("focus", (e) => showTip(e, r.tip));
      row.addEventListener("blur", hideTip);
    }
    wrap.append(row);
  }
  return wrap;
}

// One diverging bar with an uncertainty whisker, for inline use in a grid row.
export function miniBar(o, [lo, hi] = [-30, 60]) {
  const span = hi - lo;
  const pos = (v) => ((Math.max(lo, Math.min(hi, v)) - lo) / span) * 100;
  const zero = pos(0);
  return h("div", { class: "bar-track" },
    h("div", { class: "zero", style: { left: `${zero}%` } }),
    h("div", { class: `bar-fill ${o.pct < 0 ? "neg" : "pos"}`, style: { left: `${Math.min(pos(o.pct), zero)}%`, width: `${Math.max(0.8, Math.abs(pos(o.pct) - zero))}%` } }),
    h("div", { class: "whisker", style: { left: `${pos(o.low)}%`, width: `${Math.max(0.5, pos(o.high) - pos(o.low))}%` } }));
}

export function magnitudeBars(rows, { max } = {}) {
  const top = max || Math.max(1, ...rows.map((r) => r.value));
  const wrap = h("div", { class: "bars sdg-bars" });
  for (const r of rows) {
    wrap.append(h("div", { class: "bar-row" }, r.label,
      h("div", { class: "bar-track" }, h("div", { class: "bar-fill", style: { left: "0", width: `${(r.value / top) * 100}%` } })),
      h("div", { class: "bar-val" }, r.display ?? String(r.value))));
  }
  return wrap;
}

// ---------------------------------------------------------------- sparkline (single series: no legend, title names it)
export function sparkline(points, { width = 520, height = 120, format = (v) => `${(v * 100).toFixed(1)}%` } = {}) {
  if (!points.length) return h("p", { class: "muted small" }, "–");
  const padL = 40, padR = 10, padT = 10, padB = 22;
  const vals = points.map((p) => p.share);
  const max = Math.max(...vals) * 1.15 || 1;
  const x = (i) => padL + (i / (points.length - 1)) * (width - padL - padR);
  const y = (v) => padT + (1 - v / max) * (height - padT - padB);
  const line = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.share).toFixed(1)}`).join("");
  const area = `${line}L${x(points.length - 1)},${y(0)}L${x(0)},${y(0)}Z`;
  const svg = s("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "trend" },
    s("line", { x1: padL, x2: width - padR, y1: y(0), y2: y(0), stroke: "var(--axis)" }),
    s("line", { x1: padL, x2: width - padR, y1: y(max / 1.15), y2: y(max / 1.15), stroke: "var(--grid)" }),
    s("text", { x: padL - 6, y: y(max / 1.15) + 4, "text-anchor": "end", class: "radar-label" }, format(max / 1.15)),
    s("text", { x: padL - 6, y: y(0) + 4, "text-anchor": "end", class: "radar-label" }, "0"),
    s("text", { x: padL, y: height - 6, class: "radar-label" }, points[0].month),
    s("text", { x: width - padR, y: height - 6, "text-anchor": "end", class: "radar-label" }, points[points.length - 1].month),
    s("path", { d: area, fill: "var(--bar)", opacity: 0.1 }),
    s("path", { d: line, fill: "none", stroke: "var(--bar)", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }),
    s("circle", { cx: x(points.length - 1), cy: y(vals[vals.length - 1]), r: 4, fill: "var(--bar)", stroke: "var(--surface)", "stroke-width": 2 }));
  const cross = s("line", { y1: padT, y2: y(0), stroke: "var(--axis)", visibility: "hidden" });
  const overlay = s("rect", { x: padL, y: padT, width: width - padL - padR, height: y(0) - padT, fill: "transparent" });
  svg.append(cross, overlay);
  overlay.addEventListener("pointermove", (e) => {
    const box = svg.getBoundingClientRect();
    const px = ((e.clientX - box.left) / box.width) * width;
    const i = Math.max(0, Math.min(points.length - 1, Math.round(((px - padL) / (width - padL - padR)) * (points.length - 1))));
    cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
    showTip(e, () => h("div", {}, h("div", { class: "v" }, format(points[i].share)), h("div", { class: "k" }, points[i].month)));
  });
  overlay.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); hideTip(); });
  return svg;
}

export function meter(value) {
  return h("div", { class: "meter", role: "meter", "aria-valuemin": 0, "aria-valuemax": 100, "aria-valuenow": value },
    h("span", { style: { width: `${Math.max(2, Math.min(100, value))}%` } }));
}

export function heatColor(v) {
  const step = Math.min(7, Math.max(1, Math.ceil((v / 100) * 7)));
  return { bg: `var(--seq-${step})`, fg: step >= 5 ? "#ffffff" : "#1e1e1e" };
}
