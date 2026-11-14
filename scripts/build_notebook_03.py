"""Generates notebooks/03_nisar_multitrack_seasonal.ipynb (run: .venv\\Scripts\\python scripts\\build_notebook_03.py)."""
from pathlib import Path
import nbformat as nbf

cells = []
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s))
code = lambda s: cells.append(nbf.v4.new_code_cell(s))

md(r"""# 03 — NISAR multi-track, seasonal velocity of Siachen
Pakistan Glacier Intelligence Explorer · NASA Space Apps 2026 · *Dancing with the SARs*

Processes **every** NISAR GOFF file in `data/nisar/` (any track, ascending or descending), then:
1. culls & bias-corrects each pair and puts it on one common 80 m UTM grid,
2. median-stacks pairs per **season** (winter = Nov–Apr, summer = May–Oct) and per viewing geometry,
3. inverts for velocity — **3-D (east, north, up)** where both ascending and descending data exist,
   horizontal-only (surface-parallel assumption) where only one geometry exists,
4. compares seasons and validates against ITS_LIVE.

Processing code lives in `src/pgie/nisar.py` (tested by `tests/test_inversion.py`).""")

code(r'''import sys, warnings
from pathlib import Path
PROJECT_DIR = Path(r"D:\Pakistan Glacier Intelligence Explorer")
sys.path.insert(0, str(PROJECT_DIR / "src"))
warnings.filterwarnings("ignore", category=RuntimeWarning)

import numpy as np, pandas as pd, matplotlib.pyplot as plt
from pgie.common import NISAR_DIR, PROCESSED_DIR, RESULTS_DIR, FIGURES_DIR, save_tif
from pgie.nisar import find_pairs, common_grid, its_median_on_grid, process_pair, combine

OUT = PROCESSED_DIR / "nisar_combined"; OUT.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"figure.dpi": 110, "savefig.dpi": 150, "font.size": 9})

grid = common_grid()
its = its_median_on_grid(grid)          # ITS_LIVE 2017–22 median speed (from notebook 02)
ice, rock = its >= 15, its <= 3
print("Common grid:", grid.shape, grid.crs, "| ice px:", int(ice.sum()), "| rock px:", int(rock.sum()))''')

md("## 1. Inventory of NISAR pairs")
code(r'''pairs = find_pairs(NISAR_DIR)
inv = pd.DataFrame([{"pair": p.tag, "geometry": p.geometry, "frame": p.frame, "from": p.ref.date(), "to": p.sec.date(),
                     "days": round(p.days, 1), "season": p.season, "release": p.crid,
                     "size_GB": round(p.path.stat().st_size / 1e9, 2)} for p in pairs])
inv''')

md("## 2. Process every pair (crop → cull → bias → common grid)")
code(r'''results, rows = [], []
for p in pairs:
    try:
        r = process_pair(p, grid, rock_mask=rock)
    except ValueError as e:
        print("skip:", e); continue
    results.append(r)
    sp = np.hypot(r.v_at, r.v_sr)
    rows.append({"pair": p.tag, "season": p.season, "layer": r.layer,
                 "valid_on_ice_%": round(100 * np.isfinite(r.v_at[ice]).mean(), 1),
                 "slant_range_bias_m": round(r.stats["bias_sr_m"], 2),
                 "rock_noise_m_per_yr": round(r.stats["rock_noise_m_yr"], 1)})
pair_stats = pd.DataFrame(rows)
pair_stats.to_csv(RESULTS_DIR / "nisar_pair_quality.csv", index=False)
pair_stats''')

md("## 3. Seasonal stacks and velocity inversion")
code(r'''seasons = combine(results, group_by="season")
summary = []
for s, m in seasons.items():
    for k in ("ve", "vn", "vu", "speed"):
        save_tif(OUT / f"siachen_nisar_{s}_{k}.tif", m[k], grid.transform, grid.crs)
    save_tif(OUT / f"siachen_nisar_{s}_n_geometries.tif", m["n_geom"].astype("float32"), grid.transform, grid.crs)
    sp = m["speed"][ice]
    summary.append({"season": s, "pairs": m["n_pairs"], "geometries": "+".join(m["geometries"]),
                    "ice measured %": round(100 * np.isfinite(sp).mean(), 1),
                    "ice with 3-D solution %": round(100 * (m["n_geom"][ice] >= 2).mean(), 1),
                    "median ice speed m/yr": round(float(np.nanmedian(sp)), 1),
                    "p90 ice speed m/yr": round(float(np.nanpercentile(sp[np.isfinite(sp)], 90)), 1)})
season_df = pd.DataFrame(summary).sort_values("season", ascending=False)
season_df.to_csv(RESULTS_DIR / "nisar_seasonal_summary.csv", index=False)
season_df''')

md("## 4. Validation against ITS_LIVE (spatial pattern & flow direction)")
code(r'''import rasterio
from pgie.common import read_tif
from pgie.nisar import to_grid
from rasterio.warp import Resampling
from pyproj import Transformer

# ITS_LIVE median vx/vy (2017–22) rotated from ESRI:102027 axes into UTM east/north
def its_vec():
    vx, t, c = read_tif(PROCESSED_DIR / "its_live_siachen" / "siachen_2022_vx.tif")
    vxs = np.nanmedian([read_tif(PROCESSED_DIR / "its_live_siachen" / f"siachen_{y}_vx.tif")[0] for y in range(2017, 2023)], 0)
    vys = np.nanmedian([read_tif(PROCESSED_DIR / "its_live_siachen" / f"siachen_{y}_vy.tif")[0] for y in range(2017, 2023)], 0)
    tr = Transformer.from_crs(c, grid.crs, always_xy=True)
    cx, cy = t.c + t.a * vx.shape[1] / 2, t.f + t.e * vx.shape[0] / 2
    (x0, x1), (y0, y1) = tr.transform([cx, cx + 1000], [cy, cy])
    a = np.arctan2(y1 - y0, x1 - x0)
    ve, vn = vxs * np.cos(a) - vys * np.sin(a), vxs * np.sin(a) + vys * np.cos(a)
    return to_grid(ve, t, c, grid, Resampling.bilinear), to_grid(vn, t, c, grid, Resampling.bilinear)
its_ve, its_vn = its_vec()

val = []
for s, m in seasons.items():
    sel = ice & np.isfinite(m["speed"])
    fast = sel & (its >= 40)
    cosang = (m["ve"][fast] * its_ve[fast] + m["vn"][fast] * its_vn[fast]) / (m["speed"][fast] * np.hypot(its_ve[fast], its_vn[fast]))
    ang = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
    val.append({"season": s, "pixels": int(sel.sum()),
                "speed correlation r": round(np.corrcoef(m["speed"][sel], its[sel])[0, 1], 2),
                "NISAR/ITS_LIVE speed ratio": round(float(np.nanmedian(m["speed"][sel] / its[sel])), 2),
                "median direction diff (deg)": round(float(np.median(ang)), 1),
                "% within 30°": round(float((ang <= 30).mean() * 100), 1)})
val_df = pd.DataFrame(val)
val_df.to_csv(RESULTS_DIR / "nisar_seasonal_validation.csv", index=False)
val_df''')

md("## 5. Maps")
code(r'''order = [s for s in ("winter", "summer") if s in seasons]
vmax = np.nanpercentile(its[ice], 99)
fig, axes = plt.subplots(1, len(order) + 1, figsize=(5 * (len(order) + 1), 5.2), constrained_layout=True)
axes = np.atleast_1d(axes)
im = axes[0].imshow(its, cmap="viridis", vmin=0, vmax=vmax); axes[0].set_title("ITS_LIVE median 2017–2022")
for ax, s in zip(axes[1:], order):
    ax.imshow(seasons[s]["speed"], cmap="viridis", vmin=0, vmax=vmax)
    ax.set_title(f"NISAR {s} ({seasons[s]['n_pairs']} pair(s), {'+'.join(seasons[s]['geometries'])})")
for ax in axes: ax.set_xticks([]); ax.set_yticks([])
fig.colorbar(im, ax=axes, shrink=0.8, label="Horizontal speed (m/yr)")
fig.savefig(FIGURES_DIR / "nisar_seasonal_speed.png"); plt.show()''')

code(r'''if {"winter", "summer"} <= set(seasons):
    d = seasons["summer"]["speed"] - seasons["winter"]["speed"]
    d = np.where(ice, d, np.nan)
    pct = 100 * d / seasons["winter"]["speed"]
    lim = np.nanpercentile(np.abs(d), 98)
    fig, ax = plt.subplots(figsize=(7, 7))
    im = ax.imshow(d, cmap="RdBu_r", vmin=-lim, vmax=lim); ax.set_xticks([]); ax.set_yticks([])
    fig.colorbar(im, ax=ax, shrink=0.8, label="Summer − winter speed (m/yr)")
    ax.set_title(f"Seasonal speed-up · median {np.nanmedian(d):+.1f} m/yr ({np.nanmedian(pct[np.isfinite(pct) & (its >= 40)]):+.0f}% on fast ice)")
    save_tif(OUT / "siachen_nisar_summer_minus_winter.tif", d, grid.transform, grid.crs)
    fig.savefig(FIGURES_DIR / "nisar_summer_minus_winter.png"); plt.show()
else:
    print("Only one season available so far:", list(seasons), "— download pairs from the other season to see seasonal change.")''')

code(r'''for s in order:
    m = seasons[s]
    if (m["n_geom"] >= 2).any():
        vu = np.where(ice & (m["n_geom"] >= 2), m["vu"], np.nan)
        lim = np.nanpercentile(np.abs(vu), 98)
        fig, ax = plt.subplots(figsize=(7, 7))
        im = ax.imshow(vu, cmap="PuOr", vmin=-lim, vmax=lim); ax.set_xticks([]); ax.set_yticks([])
        fig.colorbar(im, ax=ax, shrink=0.8, label="Vertical velocity (m/yr, + up)")
        ax.set_title(f"NISAR {s}: vertical motion (asc + desc 3-D solution)")
        fig.savefig(FIGURES_DIR / f"nisar_{s}_vertical.png"); plt.show()
    else:
        print(f"{s}: single geometry only — no vertical solution (needs ascending + descending).")''')

md(r"""## Outputs
| What | Where |
|---|---|
| Seasonal east / north / up / speed / n-geometries GeoTIFFs | `processed/nisar_combined/` |
| Per-pair quality, seasonal summary, validation | `results/nisar_*.csv` |
| Figures | `results/figures/nisar_seasonal_*.png` |

Next: `scripts/export_web_layers.py` turns these into layers for the web app.""")

nb = nbf.v4.new_notebook(cells=cells)
nb.metadata["kernelspec"] = {"name": "pgie-venv", "display_name": "Python 3 (.venv PGIE)", "language": "python"}
out = Path(__file__).resolve().parents[1] / "notebooks" / "03_nisar_multitrack_seasonal.ipynb"
nbf.write(nb, out)
print("written", out)
