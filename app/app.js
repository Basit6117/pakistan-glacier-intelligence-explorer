/* Pakistan Glacier Intelligence Explorer — front-end
 * Full-screen globe map, fly-in intro, floating panels.
 * Reads data/manifest.json + data/pixels.bin (written by scripts/export_web_layers.py). Charts: charts.js */
"use strict";

const R = 6378137;
const SIACHEN_VIEW = { center: [77.0, 35.43], zoom: 9.5, bearing: 0, pitch: 0 };
const $ = (id) => document.getElementById(id);
const fmt = Charts.fmt;
const cssVar = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
const state = { manifest: null, pixels: null, bandIndex: {}, layerId: "its_2022", marker: null, timer: null,
                drawing: false, drawPts: [], flowData: {}, hasProfile: false, introDone: false };

const LAYER_DESC = {
  its_annual: (y) => `How fast the ice moved in ${y}, in metres per year. Yellow = fastest ice.`,
  its_dv: "Speed in 2022 minus speed in 2017. Red = moving faster now, blue = slower.",
  its_significant: "Only change larger than twice its measurement error — real change, not noise.",
  its_trend: "Average change in speed per year over 2017–2022.",
  nisar_winter: "NISAR radar, Nov 2025 – Jan 2026 (4 image pairs). Shown on glacier ice only.",
  nisar_summer: "NISAR radar, Jul – Aug 2026 (3 image pairs). Gaps where wet snow blocks radar matching.",
  nisar_seasonal: "Summer minus winter speed. Red = faster in summer, when meltwater lubricates the glacier bed.",
  its_reliability: "How precise each ITS_LIVE speed is (its error as a share of the speed).",
  nisar_conf_winter: "Green = seen from two satellite directions (full 3-D motion). Yellow = one direction only.",
  nisar_conf_summer: "Green = seen from two satellite directions (full 3-D motion). Yellow = one direction only.",
};

/* ---------------- map: starts as a globe, flies in to Siachen ---------------- */
const map = new maplibregl.Map({
  container: "map",
  style: {
    version: 8,
    projection: { type: "globe" },
    sky: { "atmosphere-blend": ["interpolate", ["linear"], ["zoom"], 0, 1, 5, 1, 7, 0] },
    sources: { imagery: { type: "raster", tileSize: 256, maxzoom: 17,
      tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
      attribution: "Imagery © Esri, Maxar, Earthstar Geographics" } },
    layers: [
      { id: "space", type: "background", paint: { "background-color": "#05080f" } },
      { id: "imagery", type: "raster", source: "imagery", paint: { "raster-saturation": -0.3, "raster-brightness-max": 0.88 } },
    ],
  },
  center: reducedMotion ? SIACHEN_VIEW.center : [62, 22], zoom: reducedMotion ? SIACHEN_VIEW.zoom : 1.4,
  attributionControl: { compact: true }, doubleClickZoom: false,
});
// Wait only for the style (not basemap tiles, which can be slow); registered before any await so it can't be missed.
const mapReady = new Promise((res) => { map.once("style.load", res); map.once("load", res); if (map.isStyleLoaded()) res(); });
map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");

/* ---------------- 3-D terrain (off by default; display only) ---------------- */
const DEM_URL = "https://elevation-tiles-prod.s3.amazonaws.com/terrarium/{z}/{x}/{y}.png";
const terrain = { on: false, errors: 0, loaded: false, orbit: null, check: null };

class ViewControl {        // map toolbar: 3D toggle · Orbit · Reset view
  onAdd() {
    const c = document.createElement("div");
    c.className = "maplibregl-ctrl maplibregl-ctrl-group view-ctrl";
    const mk = (id, text, title) => { const b = document.createElement("button"); b.type = "button"; b.id = id; b.textContent = text; b.title = title; b.setAttribute("aria-label", title); c.appendChild(b); return b; };
    mk("v-3d", "3D", "Toggle 3-D relief").addEventListener("click", () => setTerrain(!terrain.on));
    mk("v-orbit", "⟳", "Rotate once around the view (3-D only)").addEventListener("click", toggleOrbit);
    mk("v-reset", "⌂", "Reset view").addEventListener("click", resetView);
    return c;
  }
  onRemove() {}
}
map.addControl(new ViewControl(), "top-right");

function setTerrain(on) {
  terrain.on = on;
  $("terrain-on").checked = on;
  $("exag").disabled = !on;
  $("v-3d").classList.toggle("on", on); $("v-3d").setAttribute("aria-pressed", String(on));
  $("v-orbit").disabled = !on;
  clearTimeout(terrain.check);
  if (!on) {
    stopOrbit();
    map.setTerrain(null);
    map.easeTo({ pitch: 0, bearing: 0, duration: 900 });
    return;
  }
  if (!map.getSource("dem")) {
    map.addSource("dem", { type: "raster-dem", tiles: [DEM_URL], tileSize: 256, encoding: "terrarium", maxzoom: 15,
      attribution: "Terrain: AWS Terrain Tiles (Mapzen)" });
  }
  terrain.errors = 0;
  map.setTerrain({ source: "dem", exaggeration: +$("exag").value });
  map.easeTo({ pitch: 60, duration: 1200 });
  // graceful fallback: if elevation tiles keep failing, return to 2-D and say so
  terrain.check = setTimeout(() => {
    if (terrain.on && terrain.errors > 0 && !terrain.loaded) fallback2D();
  }, 12000);
}
function fallback2D() {
  setTerrain(false);
  toast("3-D relief could not load (no connection to the elevation service) — showing the normal 2-D map.");
}
map.on("error", (e) => {
  if (e.sourceId !== "dem" && !(e.source && e.source.id === "dem")) return;
  terrain.errors += 1;
  if (terrain.on && !terrain.loaded && terrain.errors >= 4) fallback2D();
});
map.on("sourcedata", (e) => { if (e.sourceId === "dem" && e.isSourceLoaded) terrain.loaded = true; });

function toggleOrbit() {
  if (terrain.orbit) return stopOrbit();
  if (!terrain.on) return;
  if (reducedMotion) return toast("Orbit is off because your system prefers reduced motion. Right-drag the map to rotate.");
  const start = performance.now(), b0 = map.getBearing(), DURATION = 16000;      // one revolution, then stop
  $("v-orbit").classList.add("on");
  const step = (t) => {
    const k = Math.min(1, (t - start) / DURATION);
    map.setBearing(b0 + 360 * k);
    if (k < 1 && terrain.orbit) terrain.orbit = requestAnimationFrame(step); else stopOrbit();
  };
  terrain.orbit = requestAnimationFrame(step);
}
function stopOrbit() {
  if (terrain.orbit) cancelAnimationFrame(terrain.orbit);
  terrain.orbit = null;
  const b = $("v-orbit"); b && b.classList.remove("on");
}
["mousedown", "wheel", "touchstart"].forEach((ev) => map.getCanvasContainer().addEventListener(ev, stopOrbit, { passive: true }));

function resetView() {
  stopOrbit();
  map.flyTo({ ...SIACHEN_VIEW, pitch: terrain.on ? 60 : 0, duration: 1200 });
}

function toast(msg) {
  const t = $("toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(toast.timer); toast.timer = setTimeout(() => (t.hidden = true), 6000);
}
map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");

async function init() {
  const [manifest, buf] = await Promise.all([
    fetch("data/manifest.json").then((r) => r.json()),
    fetch("data/pixels.bin").then((r) => r.arrayBuffer()),
  ]);
  state.manifest = manifest;
  state.pixels = new Int16Array(buf);
  manifest.bands.forEach((b, i) => (state.bandIndex[b.id] = i));
  state.flowData = Object.fromEntries(await Promise.all(
    manifest.flow.map(async (f) => [f.id, await fetch(f.url).then((r) => r.json())])));   // main thread: avoids worker URL issues
  renderKPIs();
  syncLayout();
  buildControls();
  renderHotspots();
  await mapReady;
  addLayers();
  setLayer(currentLayerId());
  showGlacierOverview();
  $("loading").hidden = true;
  playIntro();
}

/* ---------------- layout: panels sit between the real top-bar and KPI-row heights at any width ---------------- */
function syncLayout() {
  const root = document.documentElement.style;
  const measure = () => {
    root.setProperty("--top-h", document.querySelector(".topbar").offsetHeight + "px");
    root.setProperty("--kpi-h", $("kpis").offsetHeight + "px");
  };
  measure();
  const ro = new ResizeObserver(measure);
  ro.observe(document.querySelector(".topbar"));
  ro.observe($("kpis"));
}

/* ---------------- intro flight ---------------- */
function playIntro() {
  if (reducedMotion) return endIntro();
  $("skip").addEventListener("click", skipIntro);
  map.once("moveend", endIntro);
  setTimeout(() => map.flyTo({ ...SIACHEN_VIEW, duration: 7000, curve: 1.5, essential: true }), 400);
}
function skipIntro() { map.stop(); map.jumpTo(SIACHEN_VIEW); endIntro(); }
function endIntro() {
  if (state.introDone) return;
  state.introDone = true;
  document.body.classList.remove("intro");
  if (innerWidth < 760) $("panel-left").classList.add("collapsed");
}

/* ---------------- KPI tiles with honest mini-graphics ---------------- */
const SVGNS = "http://www.w3.org/2000/svg";
function svgEl(tag, attrs, parent) { const e = document.createElementNS(SVGNS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); parent && parent.appendChild(e); return e; }
function miniSpark(values, color) {            // trend sparkline: earlier years muted, last point accented
  const s = svgEl("svg", { viewBox: "0 0 58 58", class: "ring", "aria-hidden": "true" });
  const lo = Math.min(...values), hi = Math.max(...values), X = (i) => 4 + (i * 50) / (values.length - 1), Y = (v) => 46 - ((v - lo) / (hi - lo || 1)) * 30;
  svgEl("polyline", { points: values.map((v, i) => `${X(i)},${Y(v)}`).join(" "), fill: "none", stroke: cssVar("--text-muted"), "stroke-width": 2, "stroke-linejoin": "round" }, s);
  svgEl("circle", { cx: X(values.length - 1), cy: Y(values[values.length - 1]), r: 4, fill: color, stroke: cssVar("--surface-1"), "stroke-width": 2 }, s);
  return s;
}
function miniPair(a, b, ca, cb) {               // before/after bars from a shared zero baseline
  const s = svgEl("svg", { viewBox: "0 0 58 58", class: "ring", "aria-hidden": "true" });
  const m = Math.max(a, b), h = (v) => (v / m) * 40;
  svgEl("line", { x1: 8, x2: 50, y1: 50, y2: 50, stroke: cssVar("--axis"), "stroke-width": 1 }, s);
  svgEl("path", { d: bar(14, 50, 12, h(a)), fill: ca }, s);
  svgEl("path", { d: bar(32, 50, 12, h(b)), fill: cb }, s);
  return s;
}
function bar(x, base, w, h) { const r = Math.min(4, h); return `M${x},${base}V${base - h + r}Q${x},${base - h} ${x + r},${base - h}H${x + w - r}Q${x + w},${base - h} ${x + w},${base - h + r}V${base}Z`; }
function miniRing(pct, color) {                 // share of a whole: the only place a ring is honest
  const s = svgEl("svg", { viewBox: "0 0 58 58", class: "ring", "aria-hidden": "true" });
  const r = 23, c = 2 * Math.PI * r;
  svgEl("circle", { cx: 29, cy: 29, r, fill: "none", stroke: "#26354f", "stroke-width": 6 }, s);
  svgEl("circle", { cx: 29, cy: 29, r, fill: "none", stroke: color, "stroke-width": 6, "stroke-linecap": "round",
    "stroke-dasharray": `${(pct / 100) * c} ${c}`, transform: "rotate(-90 29 29)" }, s);
  svgEl("text", { x: 29, y: 33, "text-anchor": "middle" }, s).textContent = Math.round(pct) + "%";
  return s;
}

function renderKPIs() {
  const st = state.manifest.stats, a = st.its_annual || [], hot = (state.manifest.hotspots || [])[0], tiles = [];
  if (a.length) {
    const f = a[0], l = a[a.length - 1], ch = (100 * (l.glacier_median_m_yr - f.glacier_median_m_yr)) / f.glacier_median_m_yr;
    tiles.push({ graphic: miniSpark(a.map((r) => r.glacier_median_m_yr), cssVar("--series-its")), label: "Median glacier speed, " + l.year,
      value: fmt(l.glacier_median_m_yr), unit: "m/yr", dir: ch >= 0 ? "up" : "down", delta: `${ch >= 0 ? "+" : ""}${ch.toFixed(0)}% since ${f.year}` });
  }
  if (st.seasonal) {
    const s = st.seasonal;
    tiles.push({ graphic: miniPair(s.fast_ice_winter_m_yr, s.fast_ice_summer_m_yr, cssVar("--series-winter"), cssVar("--series-summer")),
      label: "Summer vs winter, fast ice", value: `${s.fast_ice_median_pct >= 0 ? "+" : ""}${fmt(s.fast_ice_median_pct)}%`, unit: "",
      dir: "up", delta: `${fmt(s.fast_ice_winter_m_yr)} → ${fmt(s.fast_ice_summer_m_yr)} m/yr (NISAR)` });
  }
  if (st.significant) {
    tiles.push({ graphic: miniRing(st.significant.speed_up_pct, cssVar("--up")), label: "Ice speeding up significantly",
      value: fmt(st.significant.speed_up_pct) + "%", unit: "", dir: "down", delta: `${fmt(st.significant.slow_down_pct)}% slowing · ${fmt(st.ice_km2)} km² ice` });
  }
  if (hot) {
    tiles.push({ graphic: miniPair(hot.speed_2017, hot.speed_2022, cssVar("--series-its17"), cssVar("--series-its")), label: "Largest change hotspot",
      value: `${hot.change_pct >= 0 ? "+" : ""}${fmt(hot.change_pct)}%`, unit: "", dir: hot.kind === "speed-up" ? "up" : "down",
      delta: `${fmt(hot.speed_2017)} → ${fmt(hot.speed_2022)} m/yr · ${fmt(hot.area_km2)} km²` });
  }
  $("kpis").replaceChildren(...tiles.map((t) => {
    const d = document.createElement("div"); d.className = "kpi glass";
    const txt = document.createElement("div"); txt.className = "txt";
    const lab = document.createElement("div"); lab.className = "label"; lab.textContent = t.label;
    const val = document.createElement("div"); val.className = "value"; val.textContent = t.value;
    if (t.unit) { const u = document.createElement("small"); u.textContent = t.unit; val.appendChild(u); }
    const del = document.createElement("div"); del.className = "delta";
    const ar = document.createElement("span"); ar.className = t.dir === "up" ? "arrow-up" : "arrow-down"; ar.textContent = t.dir === "up" ? "▲ " : "▼ ";
    del.append(ar, document.createTextNode(t.delta));
    txt.append(lab, val, del);
    d.append(t.graphic, txt);
    return d;
  }));
}

/* ---------------- controls ---------------- */
function optionList(items) {
  const have = new Set(state.manifest.layers.map((l) => l.id));
  return items.map(([id, label]) => {
    const has = have.has(id);
    return `<label class="opt ${has ? "" : "disabled"}"><input type="radio" name="layer" value="${id}" ${has ? "" : "disabled"}> ${label}</label>`;
  }).join("");
}

function buildControls() {
  const m = state.manifest;
  $("nisar-options").innerHTML = optionList([["nisar_winter", "Winter speed"], ["nisar_summer", "Summer speed"], ["nisar_seasonal", "Summer − winter change"]]);
  $("reliability-options").innerHTML = optionList([["its_reliability", "History: measurement precision"], ["nisar_conf_winter", "NISAR winter: 3-D coverage"], ["nisar_conf_summer", "NISAR summer: 3-D coverage"]]);
  m.flow.forEach((f) => $("flow").insertAdjacentHTML("beforeend", `<option value="${f.id}">${f.name}</option>`));
  $("flow").value = "";

  document.querySelectorAll("input[name=layer]").forEach((r) => r.addEventListener("change", () => setLayer(currentLayerId())));
  $("year").addEventListener("input", () => { $("year-out").value = $("year").value; document.querySelector("input[value=its_annual]").checked = true; setLayer(currentLayerId()); });
  $("play").addEventListener("click", togglePlay);
  $("opacity").addEventListener("input", () => m.layers.forEach((l) => map.getLayer(l.id) && map.setPaintProperty(l.id, "raster-opacity", +$("opacity").value)));
  $("flow").addEventListener("change", setFlow);
  $("show-hotspots").addEventListener("change", (e) => ["hotspots", "hotspot-labels"].forEach((l) => map.getLayer(l) && map.setLayoutProperty(l, "visibility", e.target.checked ? "visible" : "none")));
  $("left-toggle").addEventListener("click", () => {
    const c = $("panel-left").classList.toggle("collapsed");
    $("left-toggle").textContent = c ? "›" : "‹";
    $("left-toggle").setAttribute("aria-label", c ? "Expand panel" : "Collapse panel");
  });
  $("analysis-open").addEventListener("click", () => ($("drawer").hidden ? openDrawer() : closeDrawer()));
  $("drawer-close").addEventListener("click", closeDrawer);
  document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => selectTab(t.dataset.tab)));
  $("point-clear").addEventListener("click", clearPin);
  $("prof-trunk").addEventListener("click", () => { stopDrawing(); m.centreline && showProfile(m.centreline.geometry.coordinates, "Siachen main trunk", true); });
  $("prof-draw").addEventListener("click", () => (state.drawing ? finishDrawing() : startDrawing()));
  $("prof-clear").addEventListener("click", clearProfile);
  $("about-open").addEventListener("click", () => $("about").showModal());
  $("terrain-on").addEventListener("change", (e) => setTerrain(e.target.checked));
  $("exag").addEventListener("input", () => {
    const v = +$("exag").value;
    $("exag-out").value = v.toFixed(1) + "×";
    if (terrain.on) map.setTerrain({ source: "dem", exaggeration: v });
  });
  $("v-orbit").disabled = true;
  renderMethodology();
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Escape" || $("about").open) return;
    if (state.drawing) { stopDrawing(); clearProfile(); return; }
    clearPin(); clearProfile();
  });
}

function openDrawer(tab) {
  $("drawer").hidden = false;
  document.body.classList.add("drawer-open");
  $("analysis-open").setAttribute("aria-expanded", "true"); $("analysis-open").textContent = "Analysis ◂";
  if (tab) selectTab(tab);
  window.dispatchEvent(new Event("resize"));      // charts measure their width when visible
}
function closeDrawer() {
  $("drawer").hidden = true;
  document.body.classList.remove("drawer-open");
  $("analysis-open").setAttribute("aria-expanded", "false"); $("analysis-open").textContent = "Analysis ▸";
}
function selectTab(name) {
  document.querySelectorAll(".tab").forEach((t) => { const on = t.dataset.tab === name; t.classList.toggle("active", on); t.setAttribute("aria-selected", String(on)); });
  document.querySelectorAll(".tab-body").forEach((b) => (b.hidden = b.dataset.body !== name));
  if (name === "profile" && !state.hasProfile && state.manifest.centreline) showProfile(state.manifest.centreline.geometry.coordinates, "Siachen main trunk", false);
}

function currentLayerId() {
  const v = document.querySelector("input[name=layer]:checked").value;
  return v === "its_annual" ? `its_${$("year").value}` : v;
}
function togglePlay() {
  if (state.timer) { clearInterval(state.timer); state.timer = null; $("play").textContent = "▶"; return; }
  $("play").textContent = "⏸";
  document.querySelector("input[value=its_annual]").checked = true;
  state.timer = setInterval(() => {
    const y = +$("year").value >= 2022 ? 2017 : +$("year").value + 1;
    $("year").value = y; $("year-out").value = y; setLayer(`its_${y}`);
  }, 1100);
}

/* ---------------- map layers ---------------- */
function addLayers() {
  const m = state.manifest, empty = { type: "FeatureCollection", features: [] };
  m.layers.forEach((l) => {
    map.addSource(l.id, { type: "image", url: l.url, coordinates: m.corners });
    map.addLayer({ id: l.id, type: "raster", source: l.id, layout: { visibility: "none" },
      paint: { "raster-opacity": +$("opacity").value, "raster-fade-duration": 0, "raster-resampling": "nearest" } });
  });
  m.flow.forEach((f) => {
    map.addSource("flow_" + f.id, { type: "geojson", data: state.flowData[f.id] });
    map.addLayer({ id: "flow_" + f.id, type: "line", source: "flow_" + f.id, layout: { "line-cap": "round" },
      paint: { "line-color": "#ffffff", "line-width": 1.4, "line-opacity": 0, "line-opacity-transition": { duration: 0 } } });
  });
  map.addSource("aoi", { type: "geojson", data: { type: "Feature", geometry: { type: "Polygon", coordinates: [[...m.corners, m.corners[0]]] } } });
  map.addLayer({ id: "aoi", type: "line", source: "aoi", paint: { "line-color": "#5cc8ff", "line-width": 1, "line-dasharray": [3, 3] } });
  map.addSource("profile", { type: "geojson", data: empty });
  map.addLayer({ id: "profile-casing", type: "line", source: "profile", paint: { "line-color": "#000", "line-width": 5, "line-opacity": 0.45 } });
  map.addLayer({ id: "profile", type: "line", source: "profile", paint: { "line-color": "#ffd166", "line-width": 2.5 } });
  map.addSource("profile-cursor", { type: "geojson", data: empty });
  map.addLayer({ id: "profile-cursor", type: "circle", source: "profile-cursor",
    paint: { "circle-radius": 7, "circle-color": "#ffd166", "circle-stroke-color": "#0b1220", "circle-stroke-width": 2 } });
  map.addSource("draw-pts", { type: "geojson", data: empty });
  map.addLayer({ id: "draw-pts", type: "circle", source: "draw-pts", paint: { "circle-radius": 4, "circle-color": "#ffd166", "circle-stroke-color": "#000", "circle-stroke-width": 1 } });
  map.addSource("hotspots", { type: "geojson", data: { type: "FeatureCollection", features: (m.hotspots || []).map((h) => ({
    type: "Feature", properties: { rank: h.rank, kind: h.kind }, geometry: { type: "Point", coordinates: [h.lon, h.lat] } })) } });
  map.addLayer({ id: "hotspots", type: "circle", source: "hotspots",
    paint: { "circle-radius": 10, "circle-color": ["match", ["get", "kind"], "speed-up", "#d03b3b", "#2a78d6"], "circle-stroke-color": "#fff", "circle-stroke-width": 1.5 } });
  map.addLayer({ id: "hotspot-labels", type: "symbol", source: "hotspots",
    layout: { "text-field": ["to-string", ["get", "rank"]], "text-size": 11, "text-allow-overlap": true }, paint: { "text-color": "#fff" } });
  setFlow();

  map.on("mousemove", (e) => {
    const h = $("hover"), v = state.introDone ? valueAt(e.lngLat, state.layerId) : null;
    if (v === null || state.drawing) { h.hidden = true; return; }
    h.replaceChildren();
    const b = document.createElement("b"); b.textContent = describe(state.layerId, v);
    h.append(b, document.createTextNode("  " + layerMeta(state.layerId).name));
    h.hidden = false; h.style.left = e.originalEvent.clientX + 14 + "px"; h.style.top = e.originalEvent.clientY + 14 + "px";
  });
  map.on("mouseout", () => ($("hover").hidden = true));
  map.on("click", (e) => { if (!state.introDone) return; state.drawing ? addDrawPoint(e.lngLat) : inspect(e.lngLat); });
  map.on("dblclick", () => state.drawing && finishDrawing());
}

function setLayer(id) {
  state.layerId = id;
  state.manifest.layers.forEach((l) => map.getLayer(l.id) && map.setLayoutProperty(l.id, "visibility", l.id === id ? "visible" : "none"));
  ["aoi", ...state.manifest.flow.map((f) => "flow_" + f.id), "profile-casing", "profile", "profile-cursor", "draw-pts", "hotspots", "hotspot-labels"]
    .forEach((l) => map.getLayer(l) && map.moveLayer(l));
  renderLegend(id);
}
function setFlow() {
  const sel = $("flow").value;
  state.manifest.flow.forEach((f) => map.getLayer("flow_" + f.id) && map.setPaintProperty("flow_" + f.id, "line-opacity", f.id === sel ? 0.95 : 0));
}
const layerMeta = (id) => state.manifest.layers.find((l) => l.id === id);
const bandMeta = (id) => state.manifest.bands[state.bandIndex[id]];

function renderLegend(id) {
  const l = layerMeta(id); if (!l) return;
  const descText = id.startsWith("its_20") ? LAYER_DESC.its_annual(id.slice(4)) : LAYER_DESC[id] || "";
  const box = $("legend");
  box.replaceChildren();
  const t = document.createElement("div"); t.className = "title"; t.textContent = l.name + (l.units ? ` (${l.units})` : "");
  const d = document.createElement("div"); d.className = "desc"; d.textContent = descText;
  box.append(t, d);
  if (l.classes) {
    const c = document.createElement("div"); c.className = "classes";
    l.classes.forEach(([lab, col]) => { const r = document.createElement("div"); const sw = document.createElement("span"); sw.className = "sw"; sw.style.background = col; r.append(sw, document.createTextNode(lab)); c.appendChild(r); });
    box.appendChild(c);
  } else {
    const bar = document.createElement("div"); bar.className = "bar";
    bar.style.background = `linear-gradient(90deg,${l.legend.map(([, c], i) => `${c} ${(100 * i) / (l.legend.length - 1)}%`).join(",")})`;
    const ticks = document.createElement("div"); ticks.className = "ticks";
    [l.legend[0], l.legend[Math.floor(l.legend.length / 2)], l.legend[l.legend.length - 1]].forEach((tk) => { const s = document.createElement("span"); s.textContent = fmt(tk[0]); ticks.appendChild(s); });
    box.append(bar, ticks);
  }
}

/* ---------------- pixel lookup ---------------- */
const merc = (lng, lat) => [(R * lng * Math.PI) / 180, R * Math.log(Math.tan(Math.PI / 4 + (lat * Math.PI) / 360))];
const unmerc = (x, y) => [(x / R) * (180 / Math.PI), (2 * Math.atan(Math.exp(y / R)) - Math.PI / 2) * (180 / Math.PI)];
function valueAtXY(x, y, bandId) {
  const g = state.manifest.grid, b = state.bandIndex[bandId];
  if (b === undefined) return null;
  const c = Math.floor((x - g.x0) / g.res), r = Math.floor((g.y1 - y) / g.res);
  if (c < 0 || r < 0 || c >= g.width || r >= g.height) return null;
  const v = state.pixels[b * g.width * g.height + r * g.width + c];
  return v === g.nodata ? null : v;
}
const valueAt = (ll, bandId) => valueAtXY(...merc(ll.lng, ll.lat), bandId);
function describe(bandId, v) {
  const b = bandMeta(bandId);
  if (b && b.kind === "class") return (b.labels && b.labels[String(v)]) || "—";
  return `${fmt(v)} ${bandId === "its_trend" ? "m/yr per year" : "m/yr"}`;
}

/* ---------------- point chart ---------------- */
const pointTip = (x) => (x > 2025.7 ? (x < 2026.3 ? "NISAR · Nov 2025 – Jan 2026" : "NISAR · Jul – Aug 2026") : `ITS_LIVE · year ${Math.floor(x)}`);
function drawPointChart(series, ariaLabel) {
  Charts.legend($("point-legend"), series);
  Charts.line($("point-chart"), { series, xDomain: [2017, 2027.2], xTicks: [2017, 2019, 2021, 2023, 2025, 2027], yLabel: "Speed (m/yr)", unit: "m/yr",
    snapTolerance: 0.35, emptyText: "No measurement here — try clicking on the glacier ice", tipHead: pointTip, ariaLabel });
}

function showGlacierOverview() {        // default content: whole-glacier medians, nothing pinned on the map
  const st = state.manifest.stats, a = st.its_annual || [], ns = Object.fromEntries((st.nisar_seasons || []).map((s) => [s.season, s]));
  drawPointChart([
    { label: "ITS_LIVE yearly median", color: cssVar("--series-its"), kind: "line", markers: true,
      points: a.map((r) => ({ x: r.year + 0.5, y: r.glacier_median_m_yr })) },
    { label: "NISAR winter 2025–26", color: cssVar("--series-winter"), kind: "points", markers: true, marker: "diamond",
      points: [{ x: 2025.95, y: ns.winter ? ns.winter["median ice speed m/yr"] : null }] },
    { label: "NISAR summer 2026", color: cssVar("--series-summer"), kind: "points", markers: true, marker: "diamond",
      points: [{ x: 2026.6, y: ns.summer ? ns.summer["median ice speed m/yr"] : null }] },
  ], "Median speed of all glacier ice over time");
  $("point-title").textContent = "Whole glacier";
  $("point-sub").textContent = "Median speed of all measured glacier ice. Click the map to inspect any spot.";
  $("point-clear").hidden = true;
}

function inspect(ll, note) {
  if (state.marker) state.marker.remove();
  const el = document.createElement("div");
  el.className = "pin"; el.title = "Click to remove";
  el.innerHTML = '<svg width="26" height="34" viewBox="0 0 26 34" aria-hidden="true"><path d="M13 1C6.4 1 1 6.3 1 12.9 1 22 13 33 13 33s12-11 12-20.1C25 6.3 19.6 1 13 1z" fill="#ff9f43" stroke="#0b1220" stroke-width="2"/><circle cx="13" cy="13" r="4.5" fill="#0b1220"/></svg>';
  el.addEventListener("click", (e) => { e.stopPropagation(); clearPin(); });
  state.marker = new maplibregl.Marker({ element: el, anchor: "bottom" }).setLngLat(ll).addTo(map);
  const bands = state.manifest.bands, v = (id) => (state.bandIndex[id] === undefined ? null : valueAt(ll, id));
  const its = bands.filter((b) => /^its_20\d\d$/.test(b.id));
  drawPointChart([
    { label: "ITS_LIVE yearly speed ± error", color: cssVar("--series-its"), kind: "line", markers: true,
      points: its.map((b) => ({ x: b.t, y: v(b.id), err: v(b.id.replace("its_", "its_err_")) })) },
    { label: "NISAR winter 2025–26", color: cssVar("--series-winter"), kind: "points", markers: true, marker: "diamond", points: [{ x: 2025.95, y: v("nisar_winter") }] },
    { label: "NISAR summer 2026", color: cssVar("--series-summer"), kind: "points", markers: true, marker: "diamond", points: [{ x: 2026.6, y: v("nisar_summer") }] },
  ], "Glacier speed over time at the selected point");
  const sig = v("its_significant"), rel = v("its_reliability"), y22 = v("its_2022"), bits = [];
  if (y22 !== null) bits.push(`${fmt(y22)} m/yr in 2022`);
  if (sig !== null) bits.push(describe("its_significant", sig).toLowerCase());
  if (rel !== null) bits.push(`precision ${describe("its_reliability", rel).split(" (")[0].toLowerCase()}`);
  $("point-title").textContent = note || `${ll.lat.toFixed(3)}° N, ${ll.lng.toFixed(3)}° E`;
  $("point-sub").textContent = bits.join(" · ") || "No glacier measurement at this spot.";
  $("point-clear").hidden = false;
  openDrawer("point");
}

function clearPin() {
  if (state.marker) { state.marker.remove(); state.marker = null; }
  showGlacierOverview();
}

/* ---------------- profile ---------------- */
function startDrawing() {
  clearProfile();
  state.drawing = true; state.drawPts = [];
  $("map").classList.add("drawing");
  $("prof-draw").classList.add("active"); $("prof-draw").textContent = "Finish line";
  $("prof-sub").textContent = "Click points along a glacier, then double-click or press Finish line. Esc cancels.";
}
function addDrawPoint(ll) {
  state.drawPts.push([ll.lng, ll.lat]);
  map.getSource("draw-pts").setData({ type: "FeatureCollection", features: state.drawPts.map((c) => ({ type: "Feature", geometry: { type: "Point", coordinates: c } })) });
  if (state.drawPts.length > 1) map.getSource("profile").setData({ type: "Feature", geometry: { type: "LineString", coordinates: state.drawPts } });
  $("prof-clear").hidden = false;
}
function stopDrawing() {
  state.drawing = false;
  $("map").classList.remove("drawing");
  $("prof-draw").classList.remove("active"); $("prof-draw").textContent = "Draw a line";
}
function finishDrawing() {
  const pts = state.drawPts.slice();
  stopDrawing();
  map.getSource("draw-pts").setData({ type: "FeatureCollection", features: [] });
  if (pts.length >= 2) showProfile(pts, "Your line", true);
  else { clearProfile(); $("prof-sub").textContent = "Need at least two points — press Draw a line to try again."; }
}
function clearProfile() {
  const empty = { type: "FeatureCollection", features: [] };
  ["profile", "draw-pts", "profile-cursor"].forEach((s) => map.getSource(s) && map.getSource(s).setData(empty));
  state.hasProfile = false;
  $("prof-clear").hidden = true;
  $("prof-legend").replaceChildren();
  $("profile-chart").replaceChildren();
  $("prof-sub").textContent = "Pick the Siachen main trunk or draw your own line.";
}

function showProfile(coords, name, fit) {
  map.getSource("profile").setData({ type: "Feature", geometry: { type: "LineString", coordinates: coords } });
  const step = state.manifest.grid.res, samples = [];
  let d = 0;
  for (let i = 0; i < coords.length - 1; i++) {
    const [x0, y0] = merc(...coords[i]), [x1, y1] = merc(...coords[i + 1]);
    const seg = Math.hypot(x1 - x0, y1 - y0), k = Math.cos((coords[i][1] * Math.PI) / 180);   // Mercator → ground metres
    for (let s = 0; s < seg; s += step) samples.push({ d: (d + s * k) / 1000, x: x0 + ((x1 - x0) * s) / seg, y: y0 + ((y1 - y0) * s) / seg });
    d += seg * k;
  }
  const defs = [["its_2017", "ITS_LIVE 2017", "--series-its17"], ["its_2022", "ITS_LIVE 2022", "--series-its"],
                ["nisar_winter", "NISAR winter 2025–26", "--series-winter"], ["nisar_summer", "NISAR summer 2026", "--series-summer"]];
  const series = defs.filter(([id]) => state.bandIndex[id] !== undefined).map(([id, label, c]) => ({
    label, color: cssVar(c), kind: "line", points: smooth(samples.map((p) => ({ x: p.d, y: valueAtXY(p.x, p.y, id) })), 5) }));
  const km = d / 1000, tick = km > 40 ? 10 : km > 15 ? 5 : km > 5 ? 2 : 1;
  const ticks = []; for (let k = 0; k <= km + 1e-9; k += tick) ticks.push(k);
  state.hasProfile = true;
  $("prof-clear").hidden = false;
  openDrawer("profile");
  Charts.legend($("prof-legend"), series);
  Charts.line($("profile-chart"), {
    series, xDomain: [0, km], xTicks: ticks, xLabel: "km", yLabel: "Speed (m/yr)", unit: "m/yr", snapTolerance: 0.15,
    emptyText: "No measurements along this line", ariaLabel: `Speed along ${name}`,
    tipHead: (x) => `${fmt(x)} km along ${name.toLowerCase()}`,
    onHover: (x) => {
      const src = map.getSource("profile-cursor"); if (!src) return;
      if (x === null) { src.setData({ type: "FeatureCollection", features: [] }); return; }
      let best = samples[0]; samples.forEach((p) => { if (Math.abs(p.d - x) < Math.abs(best.d - x)) best = p; });
      src.setData({ type: "Feature", geometry: { type: "Point", coordinates: unmerc(best.x, best.y) } });
    },
  });
  $("prof-sub").textContent = `${name} · ${km.toFixed(1)} km, upper basin (left) → snout (right). Hover the chart to follow it on the map.`;
  if (fit) {
    const lons = coords.map((c) => c[0]), lats = coords.map((c) => c[1]);
    map.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]],
      { padding: { top: 100, bottom: 130, left: 320, right: 500 }, duration: 800 });
  }
}
function smooth(pts, w) {   // running median; keeps real gaps, drops isolated stray pixels (< 3 valid neighbours)
  return pts.map((p, i) => {
    if (p.y === null) return p;
    const win = pts.slice(Math.max(0, i - w), i + w + 1).map((q) => q.y).filter((v) => v !== null).sort((a, b) => a - b);
    return { x: p.x, y: win.length < 3 ? null : win[Math.floor(win.length / 2)] };
  });
}

/* ---------------- methodology panel (numbers come from the processed results) ---------------- */
function renderMethodology() {
  const st = state.manifest.stats, cell = (tr, text, cls) => { const td = document.createElement("td"); td.textContent = text; if (cls) td.className = cls; tr.appendChild(td); };
  const day = (s) => new Date(`${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}T00:00:00Z`).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  $("m-pairs").replaceChildren(...(st.pairs || []).map((p) => {
    const m = /^(\d{3})([AD])\d{3}_(\d{8})_(\d{8})$/.exec(p.pair); const tr = document.createElement("tr");
    if (!m) { cell(tr, p.pair); return tr; }
    cell(tr, String(+m[1])); cell(tr, m[2] === "A" ? "Ascending" : "Descending"); cell(tr, `${day(m[3])} → ${day(m[4])}`);
    cell(tr, p.season); cell(tr, `±${fmt(p.rock_noise_m_per_yr)} m/yr`, "num");
    return tr;
  }));
  $("m-val-rows").replaceChildren(...(st.nisar_validation || []).map((v) => {
    const tr = document.createElement("tr");
    cell(tr, v.season); cell(tr, `${fmt(v["median direction diff (deg)"])}°`, "num"); cell(tr, `${fmt(v["% within 30°"])}%`, "num"); cell(tr, fmt(v["speed correlation r"]), "num");
    return tr;
  }));
  const s = st.seasonal;
  $("m-seasonal").textContent = s ? `moved ${fmt(s.fast_ice_winter_m_yr)} m/yr in winter and ${fmt(s.fast_ice_summer_m_yr)} m/yr in summer (median ${s.fast_ice_median_pct >= 0 ? "+" : ""}${fmt(s.fast_ice_median_pct)}%), over ${fmt(s.pixels_both_km2)} km² measured in both seasons` : "";
}

/* ---------------- hotspots table ---------------- */
function renderHotspots() {
  const hs = state.manifest.hotspots || [];
  $("hotspots").replaceChildren(...hs.map((h) => {
    const tr = document.createElement("tr"); tr.tabIndex = 0;
    const up = h.kind === "speed-up";
    const c1 = document.createElement("td"); c1.textContent = h.rank;
    const c2 = document.createElement("td"); c2.className = up ? "chg-up" : "chg-down";
    const ic = document.createElement("i"); ic.textContent = up ? "▲ " : "▼ ";
    const pct = document.createElement("span"); pct.className = "pct";
    pct.textContent = h.change_pct === null ? "" : ` ${h.change_pct > 0 ? "+" : ""}${fmt(h.change_pct)}%`;
    c2.append(ic, document.createTextNode(up ? "Faster" : "Slower"), pct);
    const c3 = document.createElement("td"); c3.className = "num"; c3.textContent = `${fmt(h.area_km2)} km²`;
    const c4 = document.createElement("td"); c4.className = "num"; c4.textContent = `${fmt(h.speed_2017)} → ${fmt(h.speed_2022)} m/yr`;
    tr.append(c1, c2, c3, c4);
    const go = () => {
      document.querySelector("input[value=its_significant]").checked = true;
      setLayer("its_significant");
      stopOrbit();
      if (terrain.on) map.flyTo({ center: [h.lon, h.lat], zoom: 12, pitch: 62, bearing: map.getBearing() - 25, duration: 2200 });
      else map.flyTo({ center: [h.lon, h.lat], zoom: 11.3, duration: 1500 });
      inspect({ lng: h.lon, lat: h.lat }, `Hotspot ${h.rank}`);
      selectTab("hot");
    };
    tr.addEventListener("click", go);
    tr.addEventListener("keydown", (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), go()));
    return tr;
  }));
}

init().catch((err) => {
  $("loading").textContent = "Could not load data — run scripts/export_web_layers.py and serve the app folder (see README).";
  $("loading").hidden = false;
  document.body.classList.remove("intro");
  console.error(err);
});
