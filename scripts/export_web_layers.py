"""Export processed rasters into lightweight layers for the web app (app/data/).

Produces:
  app/data/layers/*.png   colour-mapped, transparent overlays on one Web-Mercator grid
  app/data/pixels.bin     Int16 values (m/yr) for click-to-inspect time series, band-major
  app/data/flow_*.geojson flow-direction arrows
  app/data/manifest.json  everything the front-end needs (bounds, legends, stats, band table)

Run after notebooks 02/03:   .venv\\Scripts\\python scripts\\export_web_layers.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib import colormaps
from PIL import Image
from pyproj import Transformer
from rasterio.crs import CRS
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pgie.common import AOI, PROCESSED_DIR, RESULTS_DIR, PROJECT_DIR, read_tif  # noqa: E402

APP_DATA = PROJECT_DIR / "app" / "data"
(APP_DATA / "layers").mkdir(parents=True, exist_ok=True)
ITS = PROCESSED_DIR / "its_live_siachen"
NIS = PROCESSED_DIR / "nisar_combined"
YEARS = list(range(2017, 2023))
NODATA = -32768

# ---------------------------------------------------------------- one Web-Mercator display grid
WEB = CRS.from_epsg(3857)
RES = 100.0
to_merc = Transformer.from_crs("EPSG:4326", WEB, always_xy=True)
x0, y0 = to_merc.transform(AOI["lon_min"], AOI["lat_min"])
x1, y1 = to_merc.transform(AOI["lon_max"], AOI["lat_max"])
W, H = int(np.ceil((x1 - x0) / RES)), int(np.ceil((y1 - y0) / RES))
T = from_origin(x0, y1, RES, RES)
to_ll = Transformer.from_crs(WEB, "EPSG:4326", always_xy=True)
lon_w, lat_n = to_ll.transform(x0, y1)
lon_e, lat_s = to_ll.transform(x0 + W * RES, y1 - H * RES)
CORNERS = [[lon_w, lat_n], [lon_e, lat_n], [lon_e, lat_s], [lon_w, lat_s]]


def to_web(path, resampling=Resampling.bilinear):
    a, t, c = read_tif(path)
    out = np.full((H, W), np.nan, "float32")
    reproject(a.astype("float32"), out, src_transform=t, src_crs=c, dst_transform=T, dst_crs=WEB,
              resampling=resampling, src_nodata=np.nan, dst_nodata=np.nan)
    return out


def png(arr, name, cmap, vmin, vmax, alpha_mask=None):
    norm = np.clip((arr - vmin) / (vmax - vmin), 0, 1)
    rgba = (colormaps[cmap](np.nan_to_num(norm)) * 255).astype("uint8")
    visible = np.isfinite(arr) & (alpha_mask if alpha_mask is not None else True)
    rgba[..., 3] = np.where(visible, 225, 0)
    Image.fromarray(rgba, "RGBA").save(APP_DATA / "layers" / f"{name}.png", optimize=True)
    return f"data/layers/{name}.png"


def legend(cmap, vmin, vmax, n=7):
    return [[round(vmin + (vmax - vmin) * i / (n - 1), 1),
             "#%02x%02x%02x" % tuple(int(255 * c) for c in colormaps[cmap](i / (n - 1))[:3])] for i in range(n)]


manifest = {"corners": CORNERS, "grid": {"width": W, "height": H, "x0": x0, "y1": y1, "res": RES, "nodata": NODATA},
            "provenance": {
                "ai_generated_code": True,
                "ai_generated_data_products": True,
                "disclosure": "AI-written code and AI-assisted processing produced these derived web layers; see AI_USAGE.md."
            },
            "layers": [], "bands": [], "flow": [], "stats": {}}
bands = []

# ---------------------------------------------------------------- ITS_LIVE
v_med = to_web(ITS / "siachen_v_median_2017_2022.tif")
ice = v_med >= 15
VMAX = float(np.round(np.nanpercentile(v_med[ice], 99), -1))
for y in YEARS:
    a = to_web(ITS / f"siachen_{y}_v.tif")
    manifest["layers"].append({"id": f"its_{y}", "group": "its_annual", "year": y,
                               "name": f"ITS_LIVE speed {y}", "url": png(a, f"its_{y}", "viridis", 0, VMAX, a >= 10),
                               "legend": legend("viridis", 0, VMAX), "units": "m/yr"})
    bands.append(("its_" + str(y), f"ITS_LIVE {y}", y + 0.5, a))

for fname, lid, title, cmap, units in [
    ("siachen_dv_2022_minus_2017.tif", "its_dv", "Speed change 2017 → 2022", "RdBu_r", "m/yr"),
    ("siachen_trend_m_per_yr2.tif", "its_trend", "Speed trend 2017–2022", "RdBu_r", "m/yr per year")]:
    a = to_web(ITS / fname)
    lim = float(np.round(np.nanpercentile(np.abs(a[np.isfinite(a)]), 97), 0))
    manifest["layers"].append({"id": lid, "group": "its_change", "name": title,
                               "url": png(a, lid, cmap, -lim, lim, ice), "legend": legend(cmap, -lim, lim), "units": units})
    bands.append((lid, title, None, a))

# ---------------------------------------------------------------- NISAR seasonal
season_meta = {"winter": ("NISAR winter 2025–26", 2026.0), "summer": ("NISAR summer 2026", 2026.55)}
NISAR_MAX = 800.0   # m/yr; values above this are noise for Siachen
for s, (title, tpos) in season_meta.items():
    f = NIS / f"siachen_nisar_{s}_speed.tif"
    if not f.exists():
        continue
    a = to_web(f)
    a[a > NISAR_MAX] = np.nan          # physically impossible for Siachen (ITS_LIVE p99 ≈ 250 m/yr): residual radar noise
    manifest["layers"].append({"id": f"nisar_{s}", "group": "nisar", "name": title,
                               "url": png(a, f"nisar_{s}", "viridis", 0, VMAX, (a >= 10) & ice),
                               "legend": legend("viridis", 0, VMAX), "units": "m/yr"})
    bands.append((f"nisar_{s}", title, tpos, np.where(ice, a, np.nan)))   # off-ice NISAR values are noise
f = NIS / "siachen_nisar_summer_minus_winter.tif"
if f.exists():
    a = to_web(f)
    a[np.abs(a) > NISAR_MAX] = np.nan
    lim = float(np.round(np.nanpercentile(np.abs(a[np.isfinite(a)]), 97), 0))
    manifest["layers"].append({"id": "nisar_seasonal", "group": "nisar", "name": "NISAR summer − winter",
                               "url": png(a, "nisar_seasonal", "RdBu_r", -lim, lim, ice),
                               "legend": legend("RdBu_r", -lim, lim), "units": "m/yr"})
    bands.append(("nisar_seasonal", "Summer − winter", None, a))


# ---------------------------------------------------------------- reliability, significant change, hotspots (notebook 04)
def png_classes(arr, name, classes):
    rgba = np.zeros(arr.shape + (4,), "uint8")
    for val, _, hexc in classes:
        m = np.isclose(arr, val)
        rgba[m, :3] = [int(hexc[i:i + 2], 16) for i in (1, 3, 5)]
        rgba[m, 3] = 215
    Image.fromarray(rgba, "RGBA").save(APP_DATA / "layers" / f"{name}.png", optimize=True)
    return f"data/layers/{name}.png"


CLASS_LAYERS = [
    (ITS / "siachen_reliability_class.tif", "its_reliability", "ITS_LIVE reliability", "reliability",
     [(3, "High (error ≤ 10%)", "#2ecc71"), (2, "Medium (10–25%)", "#f1c40f"), (1, "Low (> 25%)", "#e74c3c")]),
    (ITS / "siachen_significant_change.tif", "its_significant", "Significant change 2017–2022", "its_change",
     [(1, "Significant speed-up", "#e8524a"), (-1, "Significant slow-down", "#3b8fd9"), (0, "No significant change", "#9aa5b4")]),
]
for s in season_meta:
    CLASS_LAYERS.append((NIS / f"siachen_nisar_{s}_n_geometries.tif", f"nisar_conf_{s}", f"NISAR {s} confidence", "reliability",
                         [(2, "3-D: ascending + descending", "#2ecc71"), (1, "Single geometry (horizontal only)", "#f1c40f")]))
for path, lid, title, group, classes in CLASS_LAYERS:
    if not path.exists():
        continue
    a = to_web(path, Resampling.nearest)
    if lid.startswith("nisar_conf"):
        a = np.where(ice & (a >= 1), a, np.nan)
    manifest["layers"].append({"id": lid, "group": group, "name": title, "url": png_classes(a, lid, classes),
                               "classes": [[lab, col] for _, lab, col in classes], "units": ""})
    bands.append((lid, title, None, a, {"kind": "class", "labels": {str(v): lab for v, lab, _ in classes}}))

# per-year ITS_LIVE errors (for error bars in the point chart)
for y in YEARS:
    bands.append((f"its_err_{y}", f"ITS_LIVE {y} error", None, to_web(ITS / f"siachen_{y}_v_error.tif"),
                  {"hidden": True, "err_for": f"its_{y}"}))

hot_csv = RESULTS_DIR / "change_hotspots.csv"
if hot_csv.exists():
    hot = pd.read_csv(hot_csv)
    hot = hot[(hot.lon.between(AOI["lon_min"], AOI["lon_max"])) & (hot.lat.between(AOI["lat_min"], AOI["lat_max"]))]
    hot = hot.head(10).reset_index(drop=True)
    hot["rank"] = hot.index + 1          # renumber after keeping only hotspots inside the study area
    manifest["hotspots"] = hot.to_dict("records")
cl = PROCESSED_DIR / "siachen_centreline.geojson"
if cl.exists():
    manifest["centreline"] = json.loads(cl.read_text())

# ---------------------------------------------------------------- click-to-inspect values
blob = np.stack([np.where(np.isfinite(b[3]), np.clip(np.round(b[3]), -32000, 32000), NODATA) for b in bands]).astype("<i2")
(APP_DATA / "pixels.bin").write_bytes(blob.tobytes())
manifest["bands"] = [{"id": b[0], "label": b[1], "t": b[2], **(b[4] if len(b) > 4 else {})} for b in bands]


# ---------------------------------------------------------------- flow arrows
def arrows(vx_path, vy_path, name, label, step_m=1500, min_speed=20, scale_s=40.0):
    vx, t, c = read_tif(vx_path); vy, _, _ = read_tif(vy_path)
    step = max(1, int(round(step_m / abs(t.a))))
    tr = Transformer.from_crs(c, "EPSG:4326", always_xy=True)
    feats = []
    for r in range(step // 2, vx.shape[0], step):
        for k in range(step // 2, vx.shape[1], step):
            ex, ny = vx[r, k], vy[r, k]
            sp = float(np.hypot(ex, ny))
            if not np.isfinite(sp) or sp < min_speed:
                continue
            x, y = t.c + (k + 0.5) * t.a, t.f + (r + 0.5) * t.e
            L = min(scale_s * sp, 0.9 * step_m) / sp           # arrow length in metres (capped)
            x2, y2 = x + ex * L, y + ny * L
            ang = np.arctan2(ny, ex)
            hx = [x2 - 0.35 * L * sp * np.cos(ang - s) / sp for s in (0.45, -0.45)]
            hy = [y2 - 0.35 * L * sp * np.sin(ang - s) / sp for s in (0.45, -0.45)]
            pts = [tr.transform(px, py) for px, py in [(x, y), (x2, y2), (hx[0], hy[0]), (x2, y2), (hx[1], hy[1])]]
            if not (AOI["lon_min"] <= pts[0][0] <= AOI["lon_max"] and AOI["lat_min"] <= pts[0][1] <= AOI["lat_max"]):
                continue
            feats.append({"type": "Feature", "properties": {"speed": round(sp, 1)},
                          "geometry": {"type": "LineString", "coordinates": [[round(a, 5), round(b, 5)] for a, b in pts]}})
    (APP_DATA / f"flow_{name}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    manifest["flow"].append({"id": name, "name": label, "url": f"data/flow_{name}.geojson", "count": len(feats)})


vxm = np.nanmedian([read_tif(ITS / f"siachen_{y}_vx.tif")[0] for y in YEARS], 0)
vym = np.nanmedian([read_tif(ITS / f"siachen_{y}_vy.tif")[0] for y in YEARS], 0)
_, t_its, c_its = read_tif(ITS / "siachen_2022_vx.tif")
from pgie.common import save_tif  # noqa: E402
save_tif(ITS / "siachen_vx_median.tif", vxm, t_its, c_its)
save_tif(ITS / "siachen_vy_median.tif", vym, t_its, c_its)
arrows(ITS / "siachen_vx_median.tif", ITS / "siachen_vy_median.tif", "its", "ITS_LIVE flow 2017–22")
for s in season_meta:
    if (NIS / f"siachen_nisar_{s}_ve.tif").exists():
        arrows(NIS / f"siachen_nisar_{s}_ve.tif", NIS / f"siachen_nisar_{s}_vn.tif", f"nisar_{s}", f"NISAR flow ({s})")

# ---------------------------------------------------------------- headline stats for the sidebar
def csv(name):
    p = RESULTS_DIR / name
    return pd.read_csv(p).to_dict("records") if p.exists() else []


manifest["stats"] = {"its_annual": csv("its_live_siachen_annual_stats.csv"),
                     "nisar_seasons": csv("nisar_seasonal_summary.csv"),
                     "nisar_validation": csv("nisar_seasonal_validation.csv"),
                     "ice_km2": round(float(ice.sum() * RES * RES / 1e6 * np.cos(np.radians(35.4)) ** 2), 0)}
sm = NIS / "siachen_nisar_summer_minus_winter.tif"
if sm.exists():   # like-for-like: only pixels measured in BOTH seasons
    from pgie.nisar import common_grid, its_median_on_grid
    d = read_tif(sm)[0]; w = read_tif(NIS / "siachen_nisar_winter_speed.tif")[0]
    its_g = its_median_on_grid(common_grid())
    both = np.isfinite(d) & np.isfinite(w) & (w > 5)
    fast = both & (its_g >= 40)
    manifest["stats"]["seasonal"] = {
        "pixels_both_km2": round(float(both.sum() * 0.0064), 0),
        "median_diff_m_yr": round(float(np.median(d[both])), 1),
        "fast_ice_median_pct": round(float(np.median(100 * d[fast] / w[fast])), 0),
        "fast_ice_winter_m_yr": round(float(np.median(w[fast])), 0),
        "fast_ice_summer_m_yr": round(float(np.median(w[fast] + d[fast])), 0)}
manifest["stats"]["pairs"] = csv("nisar_pair_quality.csv")          # for the methodology panel
sig_path = ITS / "siachen_significant_change.tif"
if sig_path.exists():   # shares computed on the native (equal-area) grid, so they are true area fractions
    sg = read_tif(sig_path)[0]; sg = sg[np.isfinite(sg)]
    manifest["stats"]["significant"] = {"speed_up_pct": round(float(np.mean(sg == 1) * 100), 1),
                                        "slow_down_pct": round(float(np.mean(sg == -1) * 100), 1)}
(APP_DATA / "manifest.json").write_text(json.dumps(manifest, indent=1, default=lambda o: None if o != o else o))
print(f"grid {W}x{H} @ {RES} m (Web Mercator) | layers {len(manifest['layers'])} | bands {len(bands)} | "
      f"arrows {[f['count'] for f in manifest['flow']]} | pixels.bin {blob.nbytes/1e6:.1f} MB")
