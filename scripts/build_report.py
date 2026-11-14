"""Build the team handbook: docs/Pakistan_Glacier_Intelligence_Explorer_Report.docx

All numbers are read from results/ and app/data/manifest.json, so re-running this after new processing keeps
the document in sync.   Run:  .venv\\Scripts\\python scripts\\build_report.py
"""
import datetime as dt
import json
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
RES, FIG, IMG = ROOT / "results", ROOT / "results" / "figures", ROOT / "docs" / "images"
OUT = ROOT / "docs" / "Pakistan_Glacier_Intelligence_Explorer_Report.docx"
M = json.loads((ROOT / "app" / "data" / "manifest.json").read_text(encoding="utf-8"))
ST = M["stats"]
ACCENT = RGBColor(0x1C, 0x5C, 0xAB)

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
for side in ("left_margin", "right_margin"):
    setattr(sec, side, Cm(2.0))
sec.top_margin, sec.bottom_margin = Cm(1.8), Cm(1.8)
CONTENT_W = Cm(17)

st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10.5)
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
for name, size in [("Heading 1", 16), ("Heading 2", 13), ("Heading 3", 11.5)]:
    h = doc.styles[name]; h.font.name = "Calibri"; h.font.size = Pt(size); h.font.color.rgb = ACCENT


# ---------------------------------------------------------------- helpers
def para(text="", bold=False, italic=False, size=None, align=None, space_after=6, color=None):
    p = doc.add_paragraph()
    r = p.add_run(text); r.bold = bold; r.italic = italic
    if size: r.font.size = Pt(size)
    if color: r.font.color.rgb = color
    if align: p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    return p


def rich(parts, style=None):
    """parts: list of (text, bold) tuples."""
    p = doc.add_paragraph(style=style)
    for text, b in parts:
        r = p.add_run(text); r.bold = b
    p.paragraph_format.space_after = Pt(4)
    return p


def bullets(items, style="List Bullet"):
    for it in items:
        if isinstance(it, tuple):
            rich([(it[0], True), (it[1], False)], style=style)
        else:
            p = doc.add_paragraph(it, style=style); p.paragraph_format.space_after = Pt(3)


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), hex_fill)
    tcPr.append(sh)


def table(header, rows, widths=None, num_cols=()):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        c = t.rows[0].cells[i]; c.text = ""
        r = c.paragraphs[0].add_run(str(h)); r.bold = True; r.font.size = Pt(9.5); r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        shade(c, "1C5CAB")
    for k, row in enumerate(rows):
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run("" if v is None else str(v)); r.font.size = Pt(9.5)
            if i in num_cols: cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
            if k % 2: shade(cells[i], "EEF3FA")
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return t


fig_no = [0]


def figure(path, caption, width=CONTENT_W):
    if not Path(path).exists():
        para(f"[missing image: {Path(path).name}]", italic=True); return
    fig_no[0] += 1
    doc.add_picture(str(path), width=width)
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = para(f"Figure {fig_no[0]}. {caption}", italic=True, size=9, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=10,
             color=RGBColor(0x52, 0x51, 0x4E))


def callout(title, text, fill="EEF3FA"):
    t = doc.add_table(rows=1, cols=1); t.style = "Table Grid"
    c = t.rows[0].cells[0]; shade(c, fill); c.text = ""
    r = c.paragraphs[0].add_run(title + "  "); r.bold = True
    c.paragraphs[0].add_run(text)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def fmt(v, d=1):
    return "—" if v is None or (isinstance(v, float) and v != v) else (f"{v:,.0f}" if abs(v) >= 100 else f"{v:.{d}f}".rstrip("0").rstrip("."))


annual = pd.read_csv(RES / "its_live_siachen_annual_stats.csv")
seasons = pd.read_csv(RES / "nisar_seasonal_summary.csv")
val = pd.read_csv(RES / "nisar_seasonal_validation.csv")
pairs = pd.DataFrame(ST.get("pairs", []))
hot = pd.DataFrame(M.get("hotspots", []))
sea, sig = ST.get("seasonal", {}), ST.get("significant", {})
a0, a1 = annual.iloc[0], annual.iloc[-1]
pct_all = 100 * (a1.glacier_median_m_yr - a0.glacier_median_m_yr) / a0.glacier_median_m_yr

# ================================================================ title page
para("NASA Space Apps Challenge 2026 · Dancing with the SARs", size=11, color=ACCENT, space_after=40)
para("Pakistan Glacier Intelligence Explorer", bold=True, size=26, space_after=6)
para("Measuring how fast Siachen Glacier moves — and how it is changing — with NASA–ISRO NISAR radar and NASA ITS_LIVE",
     size=13, color=RGBColor(0x52, 0x51, 0x4E), space_after=24)
para("Team handbook: data, implementation, results and the web application", italic=True, size=11, space_after=6)
para(f"Version of {dt.date.today():%d %B %Y}", size=10, space_after=30)
figure(IMG / "app_05_3d_relief.png", "The finished application: Siachen Glacier in 3-D, with areas that significantly sped up "
       "between 2017 and 2022 shown in red.", width=Cm(16))
doc.add_page_break()

# ================================================================ 1. summary
doc.add_heading("1. Summary in one page", 1)
para("We built a scientific pipeline and an interactive web map that measure the surface speed of Siachen Glacier "
     "(Karakoram, northern Pakistan region) from satellite data. NISAR, the new NASA–ISRO L-band radar mission, gives us "
     "the current state (seven 12-day image pairs, Nov 2025 – Aug 2026). ITS_LIVE, NASA's global glacier-velocity record, "
     "gives the history (annual maps 2017–2022). Together they show where the glacier is moving, how fast, how that changed, "
     "and how reliable each number is.")
table(["Headline finding", "Value", "Source"], [
    [f"Median glacier speed, {int(a1.year)}", f"{fmt(a1.glacier_median_m_yr)} m/yr ({pct_all:+.0f}% since {int(a0.year)})", "ITS_LIVE"],
    ["Summer vs winter speed of fast ice (same locations)",
     f"{fmt(sea.get('fast_ice_winter_m_yr'))} → {fmt(sea.get('fast_ice_summer_m_yr'))} m/yr ({sea.get('fast_ice_median_pct', 0):+.0f}%)", "NISAR, 7 pairs"],
    ["Glacier ice that sped up beyond measurement error, 2017–2022", f"{fmt(sig.get('speed_up_pct'))}% (slowed: {fmt(sig.get('slow_down_pct'))}%)", "ITS_LIVE"],
    ["Largest change hotspot", (f"{fmt(hot.iloc[0].area_km2)} km², {fmt(hot.iloc[0].speed_2017)} → {fmt(hot.iloc[0].speed_2022)} m/yr "
                                f"({hot.iloc[0].change_pct:+.0f}%)") if len(hot) else "—", "ITS_LIVE"],
    ["NISAR flow direction vs ITS_LIVE (median difference)",
     " / ".join(f"{r.season}: {fmt(r['median direction diff (deg)'])}°" for _, r in val.iterrows()), "Validation"],
], widths=[7.5, 6, 3.5])
callout("Why it matters.", "Siachen is one of the largest glaciers outside the polar regions and feeds the Nubra–Shyok–Indus "
        "river system. Knowing how fast its ice moves, and whether it is speeding up, helps scientists understand glacier "
        "health, meltwater supply and hazards such as surges.")
callout("What it does not measure.", "Glacier thinning or thickening. Colours are horizontal ice speed; the 3-D view uses "
        "a present-day terrain model for display only. Vertical motion was computed but is too noisy (≈ ±18 m/yr) to report.",
        fill="FFF4E5")
doc.add_page_break()

# ================================================================ 2. challenge
doc.add_heading("2. The challenge and our approach", 1)
para("The 2026 Space Apps challenge “Dancing with the SARs” asks teams to build a tool that uses NISAR radar observations "
     "to track changes on Earth's surface. Our team first considered flood mapping in Sindh, then chose glaciers in "
     "northern Pakistan because NISAR's long L-band wavelength is well suited to tracking ice motion, and because a "
     "published Sentinel-1 study of Siachen exists to compare against.")
bullets([
    ("NISAR is the primary dataset: ", "every map layer labelled “NISAR” comes from the downloaded GOFF products."),
    ("ITS_LIVE is supporting context: ", "a NASA product (built from Landsat and Sentinel images) that provides the historical baseline."),
    ("Hackathon rules: ", "non-US data is allowed if public and cited; at least one NASA dataset from the challenge resources must be used — NISAR satisfies this."),
    ("No deep learning: ", "six annual maps are far too few to train a reliable model. We used transparent statistics (trend, significance tests) instead, which judges can verify."),
])
doc.add_heading("Study area", 2)
para("Siachen Glacier and its tributaries: longitude 76.75–77.30° E, latitude 35.15–35.70° N. The main trunk is ~67 km "
     "from the upper basin to the snout at 35.205° N, 77.192° E (inside our area). About "
     f"{fmt(ST.get('ice_km2'))} km² of moving ice lies in view.")

# ================================================================ 3. data
doc.add_heading("3. Data", 1)
doc.add_heading("3.1 NISAR GOFF (primary)", 2)
para("NISAR Level-2 GOFF = Geocoded pixel OFFsets. For each pair of radar images taken 12 days apart, it gives how far each "
     "80 m pixel moved along the satellite's flight direction and towards/away from the satellite. It is partly processed: "
     "it still needs cleaning, calibration and conversion to velocity (Section 5). DOI 10.5067/NIL2GOFF-B1; Beta (X05010) "
     "and Provisional (P05023) releases; downloaded from ASF Vertex.")
if len(pairs):
    rows = []
    for _, p in pairs.iterrows():
        tag = p.pair
        rows.append([int(tag[:3]), "Ascending" if tag[3] == "A" else "Descending", int(tag[4:7]),
                     f"{dt.datetime.strptime(tag[8:16], '%Y%m%d'):%d %b %Y} → {dt.datetime.strptime(tag[17:25], '%Y%m%d'):%d %b %Y}",
                     p.season, f"{fmt(p['valid_on_ice_%'])}%", f"±{fmt(p.rock_noise_m_per_yr)}"])
    table(["Track", "Direction", "Frame", "Dates (12 days)", "Season", "Ice measured", "Noise m/yr"], rows,
          widths=[1.3, 2.2, 1.3, 5.2, 1.8, 2.2, 2.0], num_cols=(5, 6))
para("Why these files: we queried the ASF catalogue for every GOFF product over Siachen (62 found). Track 55 ascending, "
     "frame 19 is the only one covering the whole glacier; track 135 descending adds a second viewing direction for a 3-D "
     "solution. Exact file names are in data/nisar_download_list.txt (paste them into ASF Vertex → List Search).", size=10)
doc.add_heading("3.2 ITS_LIVE v2.1 (history)", 2)
para("Annual glacier-velocity mosaics, 120 m, region RGI 14A (High Mountain Asia), 2017–2022, from NASA JPL. Seven "
     "variables per year = 42 GeoTIFFs: v (speed), vx, vy (direction components), v_error, vx_error, vy_error (uncertainty) "
     "and count (number of image pairs behind each pixel). These are processed velocity maps, not photographs.")
doc.add_heading("3.3 Display-only data", 2)
bullets(["Satellite basemap: Esri World Imagery (© Esri, Maxar, Earthstar Geographics).",
         "3-D relief: AWS Terrain Tiles (Mapzen Terrarium; global DEM compilation incl. SRTM). Never used in calculations."])
doc.add_heading("3.4 Resolution and coordinate systems", 2)
table(["Dataset", "Resolution", "Coordinate reference system"], [
    ["NISAR GOFF", "80 m", "WGS 84 / UTM zone 43N (EPSG:32643)"],
    ["ITS_LIVE v2.1", "120 m", "Asia North Albers Equal Area (ESRI:102027)"],
    ["Common NISAR analysis grid", "80 m", "EPSG:32643 (776 × 640 pixels over the study area)"],
    ["Web app display", "100 m", "Web Mercator (EPSG:3857)"],
], widths=[5, 2.5, 9.5])

# ================================================================ 4. implementation
doc.add_heading("4. Implementation", 1)
doc.add_heading("4.1 Project folder", 2)
tree = ("Pakistan Glacier Intelligence Explorer/\n"
        "├── data/                 raw downloads — never modified\n"
        "│   ├── its_live/2017…2022/   42 ITS_LIVE GeoTIFFs\n"
        "│   └── nisar/                7 NISAR GOFF .h5 files (~7.6 GB)\n"
        "├── notebooks/            01 inspection · 02 ITS_LIVE + first NISAR · 03 multi-track seasonal · 04 hotspots\n"
        "├── src/pgie/             processing library: common.py, nisar.py, analysis.py\n"
        "├── scripts/              export_web_layers.py · build_notebook_03/04.py · build_report.py\n"
        "├── tests/                test_inversion.py (checks the velocity maths)\n"
        "├── processed/            cropped & derived GeoTIFFs\n"
        "├── results/              CSV tables + figures/\n"
        "├── app/                  the web application (index.html, app.js, charts.js, style.css, data/)\n"
        "└── docs/                 this report + images/")
p = doc.add_paragraph(); r = p.add_run(tree); r.font.name = "Consolas"; r.font.size = Pt(8.5)
doc.add_heading("4.2 Processing pipeline", 2)
table(["Step", "What it does", "Main outputs"], [
    ["01_data_inspection", "Lists files, reads metadata, checks all 42 ITS_LIVE files exist, inspects the NISAR HDF5 structure, confirms coverage of Siachen", "results/*metadata*.csv, inventory"],
    ["02_siachen_preprocessing_velocity", "Crops ITS_LIVE to Siachen, quality filter, 2017→2022 change and per-pixel trend; first single-pair NISAR prototype", "processed/its_live_siachen/*.tif"],
    ["03_nisar_multitrack_seasonal", "Processes all 7 NISAR pairs (both tracks), seasonal stacks, ascending+descending inversion, validation vs ITS_LIVE", "processed/nisar_combined/*.tif, seasonal CSVs"],
    ["04_change_hotspots_uncertainty", "Reliability classes, significance test, hotspot detection, glacier centreline and speed profile", "hotspots CSV, centreline GeoJSON"],
    ["scripts/export_web_layers.py", "Converts results into map images, pixel values, arrows and statistics for the web app", "app/data/"],
], widths=[4.3, 8.7, 4])
para("Software: Python 3.11 (rasterio, h5py, numpy, pandas, pyproj, matplotlib) in the project's .venv; the web app is a "
     "static site using MapLibre GL 5.6 (globe + 3-D terrain) and a small custom SVG chart library — no server needed.", size=10)

# ================================================================ 5. methods
doc.add_heading("5. Methods (how the numbers are made)", 1)
doc.add_heading("5.1 From NISAR offsets to velocity", 2)
bullets([
    ("Crop: ", "read only the study-area window of each 0.9–1.2 GB file."),
    ("Clean: ", "drop pixels flagged invalid/water; signal-to-noise < 5; offsets > 30 m; pixels that disagree with their 5×5 neighbourhood median by > 2 m; final speeds > 800 m/yr."),
    ("Calibrate: ", "subtract each pair's median offset over stable rock (ITS_LIVE speed ≤ 3 m/yr) — rock should not move. Example: the first pair had a +5.1 m slant-range bias."),
    ("Geometry: ", "use the product's own radar unit vectors to turn along-track and slant-range offsets into east/north ground motion. One direction → assume flow parallel to the surface; ascending + descending → least-squares east, north and up with no assumption."),
    ("Velocity: ", "displacement ÷ 12 days × 365.25 → m/yr; pairs of the same season and direction combined by per-pixel median."),
], style="List Number")
para("The maths is verified by tests/test_inversion.py, which builds a synthetic glacier with known motion and checks that "
     "the inversion recovers it (exact without noise; ~9.5 m/yr error with 10 m/yr input noise).", size=10)
doc.add_heading("5.2 ITS_LIVE quality and change", 2)
bullets([
    "Keep a pixel-year only if ≥ 5 image pairs contributed, error ≤ 20 m/yr or ≤ 25% of speed, and speed < 1,500 m/yr.",
    "Glacier ice = median 2017–2022 speed ≥ 15 m/yr; stable rock = ≤ 3 m/yr.",
    "Trend = least-squares slope of speed vs year per pixel (≥ 4 valid years) with its standard error.",
    "Significant change = trend ≥ 2 standard errors from zero AND 2017→2022 change ≥ 2 × combined error, same direction.",
    "Hotspots = connected areas of significant change ≥ 0.25 km², ranked by area.",
    "Centreline = least-cost path through the fastest ice from the upper basin to the snout; profile lengths are geodesic.",
])
doc.add_heading("5.3 Seasons and validation", 2)
para(f"Winter = Nov–Apr (4 pairs), summer = May–Oct (3 pairs). Summer − winter is computed only where both seasons were "
     f"measured ({fmt(sea.get('pixels_both_km2'))} km²). NISAR is validated against ITS_LIVE by comparing flow direction and "
     "the spatial speed pattern (the years differ, so exact values are not expected to match).")
doc.add_page_break()

# ================================================================ 6. results
doc.add_heading("6. Results", 1)
doc.add_heading("6.1 History 2017–2022 (ITS_LIVE)", 2)
table(["Year", "Pixels kept", "Median ice speed (m/yr)", "Fastest 10% (m/yr)"],
      [[int(r.year), f"{fmt(r['kept_%'])}%", fmt(r.glacier_median_m_yr), fmt(r.glacier_p90_m_yr)] for _, r in annual.iterrows()],
      widths=[2.5, 3, 5.5, 5], num_cols=(1, 2, 3))
figure(FIG / "its_live_annual_speed.png", "Annual surface speed of Siachen and its tributaries, 2017–2022 (yellow = fastest).")
figure(FIG / "its_live_change_and_trend.png", "Left: speed change 2022 − 2017. Right: per-pixel linear trend. Red = speeding up, blue = slowing down.")
figure(FIG / "hotspots_reliability_centreline.png", "Left: measurement reliability (green high, red low). Middle: significant-change hotspots, "
       "numbered. Right: the automatically traced centreline of the main trunk.")
if len(hot):
    para("Top change hotspots inside the study area:", bold=True)
    table(["#", "Change", "Area (km²)", "Speed 2017 → 2022 (m/yr)", "Change", "Location"],
          [[int(h["rank"]), "Faster" if h.kind == "speed-up" else "Slower", fmt(h.area_km2), f"{fmt(h.speed_2017)} → {fmt(h.speed_2022)}",
            f"{h.change_pct:+.0f}%", f"{h.lat:.3f}° N, {h.lon:.3f}° E"] for _, h in hot.head(8).iterrows()],
          widths=[0.9, 1.8, 2.2, 4.3, 2, 5.8], num_cols=(2, 4))
    para("Hotspot 3, a north-eastern tributary that slowed by over 80%, matches the typical end of a glacier surge — "
         "common in the Karakoram and worth highlighting.", size=10)
figure(FIG / "centreline_profile.png", "Speed along the Siachen main trunk (upper basin on the left, snout on the right): "
       "the upper 10–30 km clearly sped up between 2017 and 2022.")

doc.add_heading("6.2 Now: NISAR 2025–26", 2)
table(["Season", "Pairs", "Directions", "Ice measured", "Ice with 3-D solution", "Median ice speed", "Fastest 10%"],
      [[r.season, int(r.pairs), r.geometries, f"{fmt(r['ice measured %'])}%", f"{fmt(r['ice with 3-D solution %'])}%",
        f"{fmt(r['median ice speed m/yr'])} m/yr", f"{fmt(r['p90 ice speed m/yr'])} m/yr"] for _, r in seasons.iterrows()],
      widths=[1.8, 1.3, 2.4, 2.3, 3, 3.1, 3.1], num_cols=(1, 3, 4, 5, 6))
figure(FIG / "nisar_seasonal_speed.png", "ITS_LIVE 2017–2022 median compared with NISAR winter and summer speed (same colour scale).")
figure(FIG / "nisar_summer_minus_winter.png", f"Seasonal speed-up: the lower trunk flows "
       f"{sea.get('fast_ice_median_pct', 0):+.0f}% faster in summer, when meltwater lubricates the glacier bed.", width=Cm(11))
para("Validation against ITS_LIVE:", bold=True)
table(["Season", "Pixels", "Flow-direction difference (median)", "Within 30°", "Speed pattern r", "NISAR / ITS_LIVE"],
      [[r.season, f"{int(r.pixels):,}", f"{fmt(r['median direction diff (deg)'])}°", f"{fmt(r['% within 30°'])}%",
        f'{r["speed correlation r"]:.2f}', f'{r["NISAR/ITS_LIVE speed ratio"]:.2f}'] for _, r in val.iterrows()],
      widths=[1.8, 2.2, 4.5, 2.3, 2.8, 3.4], num_cols=(1, 2, 3, 4, 5))
para("Winter NISAR runs at ~0.7× and summer at ~0.9× the ITS_LIVE annual average — the physically expected order "
     "(annual average sits between the slow winter and fast summer).", size=10)
doc.add_page_break()

# ================================================================ 7. app
doc.add_heading("7. The web application", 1)
para("A full-screen interactive map that anyone can use without GIS knowledge. Everything shown is generated from the "
     "results above by scripts/export_web_layers.py.")
figure(IMG / "app_01_globe_intro.png", "Opening: a 3-D globe that flies in to Siachen (with a Skip button).", width=Cm(13))
figure(IMG / "app_02_main_view.png", "Main view: layers and legend (left), headline numbers (bottom), map controls (right).")
table(["Area of the screen", "What it does"], [
    ["Top bar", "Title, About the data & methodology, Analysis button"],
    ["Left panel", "History layers (speed by year with play button, change, significant change, trend); NISAR winter/summer/seasonal change; "
                   "reliability layers; flow arrows; opacity; hotspot markers; 3-D relief and height exaggeration; legend with plain-language explanation"],
    ["Bottom tiles", "Four headline numbers with honest mini-graphics (trend sparkline, before/after bars, share-of-ice ring)"],
    ["Analysis drawer", "Speed at a point (with ± error), speed along the glacier (yellow dot follows on the map), hotspot table (click to fly)"],
    ["Map toolbar", "Zoom, compass, 3D toggle, one-turn Orbit, Reset view"],
], widths=[3.5, 13.5])
figure(IMG / "app_03_point_chart.png", "Click any spot: its 2017–2022 speed with error band, plus NISAR winter and summer values. "
       "Esc or “Clear pin” removes the pin.")
figure(IMG / "app_04_profile.png", "Speed along the glacier for 2017, 2022 and both NISAR seasons.")
figure(IMG / "app_05_3d_relief.png", "Optional 3-D relief (off by default): significant change draped on the terrain. "
       "Height exaggeration (1–2×) is visual only.")
figure(IMG / "app_06_methodology.png", "The methodology panel: data, dates, resolution, method, quality, validation, limitations.")
figure(IMG / "app_07_responsive.png", "Responsive layout tested from 320 px phones to tablets and desktops, with no horizontal scrolling.")
para("Screenshots were captured with an automated headless browser, so the satellite basemap may look softer than in a normal browser.",
     italic=True, size=9)

doc.add_heading("7.1 How to run it", 2)
bullets([
    "Open PowerShell in the project folder.",
    "Run:  .venv\\Scripts\\python -m http.server 8765 -d app",
    "Open http://127.0.0.1:8765 in Chrome or Edge (internet needed for the basemap, MapLibre and, if switched on, 3-D terrain).",
], style="List Number")
doc.add_heading("7.2 How to update after new NISAR data", 2)
bullets([
    "Put new GOFF .h5 files in data/nisar/ (keep the original file names — dates and track are read from them).",
    "In VS Code, open notebooks 03 and 04, choose the kernel “Python 3 (.venv PGIE)”, Run All.",
    "Run:  .venv\\Scripts\\python scripts\\export_web_layers.py",
    "Optional: .venv\\Scripts\\python scripts\\build_report.py regenerates this document with the new numbers.",
], style="List Number")

# ================================================================ 8. limitations
doc.add_heading("8. Limitations (say these openly)", 1)
bullets([
    "NISAR (2025–26) and ITS_LIVE (2017–22) do not overlap in time — we compare patterns, not the same period.",
    "Summer NISAR covers less ice: wet snow on the upper glacier prevents radar matching.",
    "Where only one viewing direction exists, flow is assumed parallel to the surface.",
    "Vertical motion is too noisy to report; thinning/thickening is not measured. The 3-D view does not show ice-thickness change.",
    "NISAR products are early Beta/Provisional releases and may be reprocessed by NASA/JPL.",
    "Each NISAR pair has random noise of roughly ±14–33 m/yr on stable rock; stacking pairs reduces it, so slow ice (< ~30 m/yr) is less certain than fast ice.",
])

# ================================================================ 9. glossary
doc.add_heading("9. Glossary", 1)
table(["Term", "Meaning"], [
    ["m/yr", "Metres per year — how far the ice surface moves in a year"],
    ["SAR / radar", "Synthetic Aperture Radar: a satellite that sends microwaves and records echoes; works through cloud and at night"],
    ["L-band", "NISAR's ~24 cm radar wavelength; penetrates snow and keeps coherence well over ice"],
    ["GOFF", "Geocoded pixel OFFsets — NISAR product giving how far each pixel moved between two dates"],
    ["Ascending / descending", "Satellite flying north / south; they view the glacier from opposite sides"],
    ["Along-track / slant-range", "Movement along the satellite's path / towards-or-away from the satellite"],
    ["Stable rock", "Bare ground that should not move — used to calibrate and to measure noise"],
    ["Significant change", "Change larger than twice its measurement uncertainty"],
    ["Hotspot", "A connected area (≥ 0.25 km²) of significant change"],
    ["CRS", "Coordinate reference system — how map coordinates relate to places on Earth"],
], widths=[4, 13])

doc.add_heading("10. Data credits", 1)
bullets([
    "NISAR L2 GOFF: NASA/JPL–ISRO, distributed by the Alaska Satellite Facility DAAC. DOI 10.5067/NIL2GOFF-B1.",
    "ITS_LIVE v2.1: NASA MEaSUREs Inter-mission Time Series of Land Ice Velocity and Elevation, JPL.",
    "Terrain: AWS Terrain Tiles (Mapzen). Basemap: Esri, Maxar, Earthstar Geographics.",
])

OUT.parent.mkdir(exist_ok=True)
doc.save(OUT)
print("saved", OUT, f"({OUT.stat().st_size / 1e6:.1f} MB, {fig_no[0]} figures)")
