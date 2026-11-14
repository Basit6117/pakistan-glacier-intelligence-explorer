/* Minimal responsive SVG line chart with crosshair + tooltip.
 * Specs (dataviz skill): 2px lines, ≥8px markers with 2px surface ring, hairline solid grid,
 * error as a 10% wash, one y-axis, crosshair snaps to nearest x, one tooltip lists every series. */
"use strict";
const Charts = (() => {
  const NS = "http://www.w3.org/2000/svg";
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const el = (tag, attrs = {}, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
    if (parent) parent.appendChild(e);
    return e;
  };
  const niceMax = (v) => {
    if (!(v > 0)) return 10;
    const p = Math.pow(10, Math.floor(Math.log10(v))), n = v / p;
    const steps = [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10];   // fine steps → axis top close to the data
    return steps.find((s) => n <= s) * p;
  };
  const fmt = (v) => (v === null || v === undefined || Number.isNaN(v) ? "—" : Math.abs(v) >= 100 ? Math.round(v).toLocaleString() : (+v).toFixed(1).replace(/\.0$/, ""));

  const tip = () => document.getElementById("chart-tip");
  function showTip(evt, head, rows) {
    const t = tip();
    t.replaceChildren();
    const h = document.createElement("div"); h.className = "head"; h.textContent = head; t.appendChild(h);
    rows.forEach((r) => {
      const row = document.createElement("div"); row.className = "row";
      const key = document.createElement("i");
      key.className = r.marker === "diamond" ? "key-diamond" : "key-line";
      key.style.background = r.color;
      const b = document.createElement("b"); b.textContent = r.value;
      const s = document.createElement("span"); s.textContent = r.label;
      row.append(key, b, s); t.appendChild(row);
    });
    t.hidden = false;
    const pad = 14, w = t.offsetWidth, hgt = t.offsetHeight;
    let x = evt.clientX + pad, y = evt.clientY + pad;
    if (x + w > innerWidth - 8) x = evt.clientX - w - pad;
    if (y + hgt > innerHeight - 8) y = evt.clientY - hgt - pad;
    t.style.left = x + "px"; t.style.top = y + "px";
  }
  const hideTip = () => (tip().hidden = true);

  const registry = new Map();   // container → config, re-rendered on resize
  const ro = new ResizeObserver((entries) => entries.forEach((e) => registry.has(e.target) && draw(e.target, registry.get(e.target))));

  function line(container, cfg) {
    if (!registry.has(container)) ro.observe(container);
    registry.set(container, cfg);
    draw(container, cfg);
  }

  function draw(container, cfg) {
    container.replaceChildren();
    const W = Math.max(240, container.clientWidth), H = Math.max(160, container.clientHeight);
    const M = { l: 46, r: 14, t: 10, b: 34 };
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": cfg.ariaLabel || "chart" }, container);
    const series = cfg.series.filter((s) => s.points.some((p) => p.y !== null));
    if (!series.length) {
      const t = el("text", { x: W / 2, y: H / 2, "text-anchor": "middle", class: "empty" }, svg);
      t.textContent = cfg.emptyText || "No data";
      return;
    }
    const [x0, x1] = cfg.xDomain;
    // robust scale: 99th percentile, so a stray outlier can't flatten the chart (clipped values stay in the tooltip)
    const ys = series.flatMap((s) => s.points.filter((p) => p.y !== null).map((p) => p.y + (p.err || 0))).sort((a, b) => a - b);
    const yMaxData = ys.length < 20 ? ys[ys.length - 1] : ys[Math.floor(0.99 * (ys.length - 1))];
    const yMax = niceMax(yMaxData * 1.08);
    const X = (x) => M.l + ((x - x0) / (x1 - x0)) * (W - M.l - M.r);
    const Y = (y) => H - M.b - (Math.max(0, y) / yMax) * (H - M.t - M.b);
    const surface = css("--surface-1"), grid = css("--grid"), axis = css("--axis");

    // grid + y ticks: pick a division count whose step is a round number (1, 2, 2.5, 5 × 10^k)
    const isRound = (s) => { const p = Math.pow(10, Math.floor(Math.log10(s))); return [1, 2, 2.5, 5, 10].some((n) => Math.abs(s / p - n) < 1e-9); };
    const nDiv = [4, 5, 3, 6, 2].find((n) => isRound(yMax / n)) || 4;
    for (let i = 0; i <= nDiv; i++) {
      const v = (yMax * i) / nDiv;
      el("line", { x1: M.l, x2: W - M.r, y1: Y(v), y2: Y(v), stroke: i === 0 ? axis : grid, "stroke-width": 1 }, svg);
      el("text", { x: M.l - 8, y: Y(v) + 4, "text-anchor": "end" }, svg).textContent = fmt(v);
    }
    const yl = el("text", { x: 12, y: M.t + (H - M.t - M.b) / 2, "text-anchor": "middle", transform: `rotate(-90 12 ${M.t + (H - M.t - M.b) / 2})` }, svg);
    yl.textContent = cfg.yLabel || "";
    (cfg.xTicks || []).forEach((xt) => {
      el("text", { x: X(xt), y: H - M.b + 18, "text-anchor": "middle" }, svg).textContent = cfg.xFormat ? cfg.xFormat(xt) : xt;
    });
    if (cfg.xLabel) el("text", { x: W - M.r, y: H - 4, "text-anchor": "end" }, svg).textContent = cfg.xLabel;

    // plot-area clip, so a clipped outlier never draws over the axes (its value stays in the tooltip)
    const clipId = "clip" + Math.random().toString(36).slice(2);
    const defs = el("defs", {}, svg), cp = el("clipPath", { id: clipId }, defs);
    el("rect", { x: M.l - 6, y: M.t - 6, width: W - M.l - M.r + 12, height: H - M.t - M.b + 12 }, cp);
    const plot = el("g", { "clip-path": `url(#${clipId})` }, svg);

    // error washes first, then lines, then markers on top
    series.forEach((s) => {
      const pts = s.points.filter((p) => p.y !== null && p.err);
      if (s.kind !== "line" || pts.length < 2) return;
      const up = pts.map((p) => `${X(p.x)},${Y(p.y + p.err)}`), dn = pts.slice().reverse().map((p) => `${X(p.x)},${Y(Math.max(0, p.y - p.err))}`);
      el("polygon", { points: [...up, ...dn].join(" "), fill: s.color, "fill-opacity": 0.12 }, plot);
    });
    series.forEach((s) => {
      if (s.kind !== "line") return;
      let d = "", pen = false;
      s.points.forEach((p) => { if (p.y === null) { pen = false; return; } d += `${pen ? "L" : "M"}${X(p.x).toFixed(1)},${Y(p.y).toFixed(1)}`; pen = true; });
      el("path", { d, fill: "none", stroke: s.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, plot);
    });
    series.forEach((s) => {
      if (!s.markers) return;
      s.points.filter((p) => p.y !== null).forEach((p) => {
        if (s.marker === "diamond") {
          const x = X(p.x), y = Y(p.y), r = 6;
          el("polygon", { points: `${x},${y - r} ${x + r},${y} ${x},${y + r} ${x - r},${y}`, fill: s.color, stroke: surface, "stroke-width": 2 }, plot);
        } else {
          el("circle", { cx: X(p.x), cy: Y(p.y), r: 4.5, fill: s.color, stroke: surface, "stroke-width": 2 }, plot);
        }
      });
    });

    // crosshair + tooltip
    const cross = el("line", { y1: M.t, y2: H - M.b, stroke: css("--text-muted"), "stroke-width": 1, visibility: "hidden" }, svg);
    const xs = [...new Set(series.flatMap((s) => s.points.filter((p) => p.y !== null).map((p) => p.x)))].sort((a, b) => a - b);
    const hit = el("rect", { x: M.l, y: M.t, width: W - M.l - M.r, height: H - M.t - M.b, fill: "transparent" }, svg);
    hit.addEventListener("pointermove", (evt) => {
      const r = svg.getBoundingClientRect();
      const px = ((evt.clientX - r.left) / r.width) * W;
      const xv = x0 + ((px - M.l) / (W - M.l - M.r)) * (x1 - x0);
      let best = xs[0];
      xs.forEach((x) => { if (Math.abs(x - xv) < Math.abs(best - xv)) best = x; });
      cross.setAttribute("x1", X(best)); cross.setAttribute("x2", X(best)); cross.setAttribute("visibility", "visible");
      const tol = cfg.snapTolerance ?? Infinity;
      const rows = series.map((s) => {
        let near = null;
        s.points.forEach((p) => { if (p.y !== null && Math.abs(p.x - best) <= tol && (!near || Math.abs(p.x - best) < Math.abs(near.x - best))) near = p; });
        return near && { color: s.color, marker: s.marker, label: s.label,
          value: `${fmt(near.y)}${near.err ? " ± " + fmt(near.err) : ""} ${cfg.unit || ""}` };
      }).filter(Boolean);
      showTip(evt, cfg.tipHead ? cfg.tipHead(best) : String(best), rows);
      cfg.onHover && cfg.onHover(best);
    });
    hit.addEventListener("pointerleave", () => { cross.setAttribute("visibility", "hidden"); hideTip(); cfg.onHover && cfg.onHover(null); });
  }

  function legend(container, series) {
    container.replaceChildren();
    series.forEach((s) => {
      const span = document.createElement("span");
      const key = document.createElement("i");
      key.className = s.marker === "diamond" ? "key-diamond" : s.kind === "line" ? "key-line" : "key-dot";
      key.style.background = s.color;
      const t = document.createElement("span"); t.textContent = s.label;
      span.append(key, t); container.appendChild(span);
    });
  }

  return { line, legend, fmt };
})();
