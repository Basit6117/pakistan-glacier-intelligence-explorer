"""Create the seven-slide NASA Space Apps project demonstration deck."""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "Pakistan_Glacier_Intelligence_Explorer_Demo.pptx"
IMG = ROOT / "docs" / "images"
FIG = ROOT / "results" / "figures"

NAVY = RGBColor(7, 17, 35)
NAVY_2 = RGBColor(12, 29, 52)
ICE = RGBColor(139, 220, 255)
WHITE = RGBColor(245, 249, 255)
MUTED = RGBColor(178, 197, 218)
ORANGE = RGBColor(255, 174, 76)
RED = RGBColor(239, 93, 93)
GREEN = RGBColor(91, 214, 159)


def rgb(hex_value):
    return RGBColor.from_string(hex_value.replace("#", "").upper())


prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]


def box(slide, x, y, w, h, fill=None, line=None, radius=False):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill or NAVY
    shape.line.color.rgb = line or (fill or NAVY)
    if radius:
        shape.adjustments[0] = 0.08
    return shape


def text(slide, value, x, y, w, h, size=18, color=WHITE, bold=False,
         font="Aptos", align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP,
         margin=0.04, italic=False):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(margin)
    tf.margin_right = Inches(margin)
    tf.margin_top = Inches(margin)
    tf.margin_bottom = Inches(margin)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = value
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    return shape


def rich_text(slide, runs, x, y, w, h, size=18, color=WHITE, align=PP_ALIGN.LEFT):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(0.04)
    tf.margin_right = Inches(0.04)
    tf.margin_top = Inches(0.04)
    tf.margin_bottom = Inches(0.04)
    p = tf.paragraphs[0]
    p.alignment = align
    for value, bold, run_color in runs:
        run = p.add_run()
        run.text = value
        run.font.name = "Aptos"
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = run_color or color
    return shape


def add_picture(slide, path, x, y, w, h, crop=False):
    path = str(path)
    if crop:
        return slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(w), Inches(h))
    return slide.shapes.add_picture(path, Inches(x), Inches(y), width=Inches(w))


def base(title, number, kicker=None):
    slide = prs.slides.add_slide(blank)
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = NAVY
    box(slide, 0, 0, 13.333, 0.08, fill=ICE, line=ICE)
    if kicker:
        text(slide, kicker.upper(), 0.65, 0.35, 5.5, 0.25, size=10, color=ICE, bold=True)
    text(slide, title, 0.65, 0.63, 8.8, 0.58, size=27, color=WHITE, bold=True)
    text(slide, f"{number} / 7", 12.0, 0.42, 0.65, 0.25, size=10, color=MUTED, bold=True, align=PP_ALIGN.RIGHT)
    box(slide, 0.65, 1.28, 1.0, 0.05, fill=ORANGE, line=ORANGE)
    text(slide, "Pakistan Glacier Intelligence Explorer  ·  NASA Space Apps 2026", 0.65, 7.12, 8.5, 0.2, size=8, color=MUTED)
    return slide


def pill(slide, label, x, y, w, color=ICE):
    box(slide, x, y, w, 0.34, fill=NAVY_2, line=color, radius=True)
    text(slide, label, x + 0.08, y + 0.06, w - 0.16, 0.2, size=9, color=color, bold=True, align=PP_ALIGN.CENTER)


def stat_card(slide, value, label, x, y, w, accent=ICE):
    box(slide, x, y, w, 1.05, fill=NAVY_2, line=rgb("294461"), radius=True)
    text(slide, value, x + 0.16, y + 0.13, w - 0.32, 0.42, size=25, color=accent, bold=True)
    text(slide, label, x + 0.16, y + 0.62, w - 0.32, 0.25, size=10, color=MUTED)


# 1 — title
slide = prs.slides.add_slide(blank)
slide.background.fill.solid()
slide.background.fill.fore_color.rgb = NAVY
add_picture(slide, IMG / "app_05_3d_relief.png", 6.72, 0, 6.61, 7.5)
box(slide, 6.72, 0, 2.2, 7.5, fill=NAVY, line=NAVY)
box(slide, 0, 0, 13.333, 0.08, fill=ICE, line=ICE)
text(slide, "NASA SPACE APPS CHALLENGE 2026", 0.72, 0.62, 5.6, 0.3, size=11, color=ICE, bold=True)
text(slide, "Pakistan Glacier\nIntelligence Explorer", 0.68, 1.28, 6.4, 1.55, size=32, color=WHITE, bold=True)
text(slide, "How fast is Siachen Glacier moving — and is it changing?", 0.72, 3.15, 5.65, 0.85, size=19, color=ORANGE, bold=True)
text(slide, "A transparent satellite-data pipeline and interactive map for one of the hardest glaciers on Earth to monitor.", 0.72, 4.25, 5.55, 0.82, size=15, color=MUTED)
pill(slide, "DANCING WITH THE SARS", 0.72, 5.55, 2.35, color=ORANGE)
text(slide, "Muhammad Awais  ·  Abdullah Zunorain  ·  Abdul Basit", 0.72, 6.45, 5.9, 0.25, size=10, color=WHITE)
text(slide, "NASA–ISRO NISAR  +  NASA ITS_LIVE", 0.72, 6.8, 4.6, 0.22, size=9, color=ICE, bold=True)

# 2 — problem
slide = base("The problem: a glacier that is vital, remote, and changing", 2, "Why this matters")
add_picture(slide, IMG / "app_01_globe_intro.png", 7.85, 1.62, 4.85, 2.62)
box(slide, 7.85, 4.43, 4.85, 1.34, fill=NAVY_2, line=rgb("294461"), radius=True)
text(slide, "Siachen Glacier", 8.12, 4.7, 2.7, 0.3, size=20, color=ICE, bold=True)
text(slide, "≈67 km main trunk  ·  ≈753 km² of moving ice", 8.12, 5.12, 4.1, 0.25, size=12, color=WHITE)
text(slide, "Northern Pakistan  ·  Karakoram", 8.12, 5.47, 3.3, 0.22, size=10, color=MUTED)
items = [
    ("01", "Field measurements are dangerous and sparse at 4,000–7,000 m."),
    ("02", "Clouds and darkness make optical monitoring unreliable."),
    ("03", "Decision-makers need more than a raw radar file: they need where, how fast, and how certain."),
]
for i, (n, value) in enumerate(items):
    yy = 1.75 + i * 1.42
    text(slide, n, 0.78, yy, 0.48, 0.32, size=17, color=ORANGE, bold=True)
    text(slide, value, 1.42, yy - 0.02, 5.75, 0.7, size=18, color=WHITE, bold=(i == 2))
text(slide, "The question we answer:", 0.78, 6.0, 2.5, 0.25, size=11, color=ICE, bold=True)
text(slide, "Where is the ice moving, how is it changing, and can we trust the number?", 0.78, 6.32, 6.8, 0.42, size=17, color=WHITE, bold=True)

# 3 — solution
slide = base("The solution: turn NASA radar into a map anyone can use", 3, "Our approach")
add_picture(slide, IMG / "app_02_main_view.png", 6.75, 1.55, 5.92, 3.35)
box(slide, 6.75, 5.1, 5.92, 1.15, fill=NAVY_2, line=rgb("294461"), radius=True)
text(slide, "One interface, two time scales", 7.02, 5.32, 3.4, 0.25, size=15, color=ICE, bold=True)
text(slide, "NISAR shows now; ITS_LIVE shows the 2017–2022 history.", 7.02, 5.68, 4.9, 0.25, size=12, color=WHITE)
cards = [
    ("NOW", "7 NISAR GOFF pairs\nNov 2025 – Aug 2026", ICE),
    ("HISTORY", "42 NASA ITS_LIVE maps\n2017 – 2022", ORANGE),
    ("TRUST", "Errors, quality layers,\nvalidation, limitations", GREEN),
]
for i, (head, body, accent) in enumerate(cards):
    xx = 0.76 + i * 1.96
    box(slide, xx, 1.75, 1.72, 2.52, fill=NAVY_2, line=rgb("294461"), radius=True)
    text(slide, head, xx + 0.13, 1.98, 1.45, 0.25, size=12, color=accent, bold=True)
    text(slide, body, xx + 0.13, 2.47, 1.45, 0.7, size=13, color=WHITE, bold=True)
    box(slide, xx + 0.13, 3.62, 1.45, 0.04, fill=accent, line=accent)
text(slide, "The result is not a black box: every headline number can be traced to a dataset, method, uncertainty estimate, and map layer.", 0.78, 4.85, 5.45, 1.0, size=17, color=MUTED)

# 4 — method
slide = base("From radar offsets to defensible glacier velocity", 4, "How it works")
steps = [
    ("1", "COLLECT", "NISAR GOFF offsets\n80 m pixels · 12-day pairs"),
    ("2", "CLEAN + CALIBRATE", "Remove bad matches\nCorrect stable-rock bias"),
    ("3", "SOLVE", "Radar geometry →\neast / north / up motion"),
    ("4", "VALIDATE", "Compare with ITS_LIVE\nShow uncertainty honestly"),
]
for i, (num, head, body) in enumerate(steps):
    xx = 0.72 + i * 3.08
    box(slide, xx, 1.75, 2.62, 2.38, fill=NAVY_2, line=rgb("294461"), radius=True)
    box(slide, xx + 0.18, 1.98, 0.48, 0.48, fill=ORANGE if i == 1 else ICE, line=ORANGE if i == 1 else ICE, radius=True)
    text(slide, num, xx + 0.18, 2.06, 0.48, 0.22, size=15, color=NAVY, bold=True, align=PP_ALIGN.CENTER)
    text(slide, head, xx + 0.18, 2.72, 2.15, 0.25, size=12, color=ICE, bold=True)
    text(slide, body, xx + 0.18, 3.17, 2.15, 0.55, size=13, color=WHITE)
    if i < 3:
        text(slide, "→", xx + 2.7, 2.62, 0.35, 0.35, size=22, color=ORANGE, bold=True, align=PP_ALIGN.CENTER)
add_picture(slide, IMG / "app_06_methodology.png", 0.72, 4.58, 4.15, 2.12)
box(slide, 5.2, 4.58, 7.45, 2.12, fill=NAVY_2, line=rgb("294461"), radius=True)
text(slide, "Built for scientific honesty", 5.52, 4.88, 3.6, 0.28, size=17, color=GREEN, bold=True)
bullets = [
    "Stable rock provides a per-pair bias correction.",
    "Ascending + descending views enable a 3-D solution where they overlap.",
    "Significant change requires both a trend test and an error threshold.",
    "A synthetic inversion test recovers known motion: ALL PASSED.",
]
for i, item in enumerate(bullets):
    text(slide, "•  " + item, 5.52, 5.28 + i * 0.3, 6.6, 0.24, size=11, color=WHITE)

# 5 — findings
slide = base("What the data reveals", 5, "Results")
add_picture(slide, FIG / "nisar_summer_minus_winter.png", 0.72, 1.6, 5.28, 3.03)
add_picture(slide, FIG / "its_live_change_and_trend.png", 6.25, 1.6, 5.98, 3.03)
stat_card(slide, "+44%", "faster summer speed on fast ice\n63 → 94 m/yr", 0.72, 5.04, 2.78, ORANGE)
stat_card(slide, "21.2%", "of glacier ice significantly sped up\n2017–2022", 3.72, 5.04, 2.78, RED)
stat_card(slide, "17.6 km²", "largest significant hotspot\n117 → 173 m/yr", 6.72, 5.04, 2.78, ICE)
stat_card(slide, "7° / 10°", "NISAR flow-direction difference\nwinter / summer vs ITS_LIVE", 9.72, 5.04, 2.78, GREEN)

# 6 — product and impact
slide = base("A working product, not just an analysis", 6, "Impact")
add_picture(slide, IMG / "app_03_point_chart.png", 0.72, 1.6, 3.62, 2.42)
add_picture(slide, IMG / "app_04_profile.png", 4.58, 1.6, 3.62, 2.42)
add_picture(slide, IMG / "app_07_responsive.png", 8.44, 1.6, 3.62, 2.42)
features = [
    ("EXPLORE", "Click any point to see speed through time and measurement error."),
    ("COMPARE", "Switch between annual history, NISAR seasons, trends, and reliability."),
    ("ACT", "Hotspots identify where scientists and local planners should look first."),
]
for i, (head, body) in enumerate(features):
    yy = 4.45 + i * 0.68
    text(slide, head, 0.82, yy, 1.35, 0.22, size=11, color=ORANGE if i == 2 else ICE, bold=True)
    text(slide, body, 2.25, yy - 0.02, 9.65, 0.34, size=13, color=WHITE)
text(slide, "Designed for researchers, educators, decision-makers, and anyone who needs a clear answer without GIS software.", 0.82, 6.55, 11.6, 0.32, size=15, color=MUTED, italic=True)

# 7 — close
slide = base("The takeaway: make hidden glacier change visible", 7, "Demonstration")
add_picture(slide, IMG / "app_05_3d_relief.png", 7.82, 1.6, 4.85, 4.65)
text(slide, "A glacier-monitoring workflow that combines:", 0.78, 1.78, 5.8, 0.3, size=18, color=WHITE, bold=True)
for i, line in enumerate([
    "NASA–ISRO NISAR radar for current seasonal motion",
    "NASA ITS_LIVE for a six-year historical baseline",
    "Transparent science, uncertainty, and validation",
    "An accessible web map for real-world exploration",
]):
    text(slide, "✓  " + line, 0.92, 2.35 + i * 0.52, 6.2, 0.3, size=15, color=ICE if i != 2 else GREEN, bold=(i == 2))
box(slide, 0.78, 4.72, 6.35, 1.2, fill=NAVY_2, line=ORANGE, radius=True)
text(slide, "Explore the live application", 1.06, 4.96, 2.8, 0.25, size=13, color=ORANGE, bold=True)
text(slide, "https://basit6117.github.io/pakistan-glacier-intelligence-explorer/", 1.06, 5.34, 5.75, 0.28, size=11, color=WHITE, bold=True)
text(slide, "AI use is declared in the repository. NASA data credits and limitations are included in the app.", 0.8, 6.38, 6.45, 0.3, size=9, color=MUTED)

prs.save(OUT)
print(OUT)
