"""Create a captioned, narration-ready 30-second demonstration video."""
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "images"
FIG = ROOT / "results" / "figures"
FRAME_DIR = ROOT / ".demo_video_frames"
OUT = ROOT / "Pakistan_Glacier_Intelligence_Explorer_Demo.mp4"

W, H = 1920, 1080
BG = (7, 17, 35)
NAVY_2 = (12, 29, 52)
WHITE = (245, 249, 255)
MUTED = (178, 197, 218)
ICE = (139, 220, 255)
ORANGE = (255, 174, 76)
GREEN = (91, 214, 159)


def font(size, bold=False):
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def fit_image(path, max_w, max_h):
    image = Image.open(path).convert("RGB")
    ratio = min(max_w / image.width, max_h / image.height)
    resized = image.resize((int(image.width * ratio), int(image.height * ratio)), Image.Resampling.LANCZOS)
    return resized


def rounded(draw, xy, radius, fill, outline=None, width=2):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def draw_wrapped(draw, value, xy, width, fnt, fill, spacing=8):
    words = value.split()
    lines, line = [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=fnt)[2] <= width:
            line = candidate
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    draw.multiline_text(xy, "\n".join(lines), font=fnt, fill=fill, spacing=spacing)


def make_scene(index, title, caption, image_paths, accent=ICE, duration=4.0):
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, W, 14), fill=ICE)
    draw.text((86, 62), title, font=font(54, True), fill=WHITE)
    draw.rectangle((86, 146, 230, 154), fill=ORANGE)
    draw_wrapped(draw, caption, (86, 190), 720, font(31), MUTED, spacing=12)

    if len(image_paths) == 1:
        shot = fit_image(image_paths[0], 930, 690)
        x, y = 880 + (930 - shot.width) // 2, 230 + (690 - shot.height) // 2
        rounded(draw, (x - 16, y - 16, x + shot.width + 16, y + shot.height + 16), 24, NAVY_2, accent, 3)
        image.paste(shot, (x, y))
    else:
        slot_w, slot_h = 440, 290
        for i, path in enumerate(image_paths):
            shot = fit_image(path, slot_w, slot_h)
            x = 875 + (i % 2) * 485
            y = 260 + (i // 2) * 345
            rounded(draw, (x - 12, y - 12, x + slot_w + 12, y + slot_h + 12), 20, NAVY_2, accent, 3)
            image.paste(shot, (x + (slot_w - shot.width) // 2, y + (slot_h - shot.height) // 2))
    draw.text((86, 964), f"PAKISTAN GLACIER INTELLIGENCE EXPLORER   •   {index:02d}/07", font=font(18, True), fill=accent)
    return image, duration


def main():
    if FRAME_DIR.exists():
        shutil.rmtree(FRAME_DIR)
    FRAME_DIR.mkdir()

    scenes = [
        make_scene(
            1,
            "Pakistan Glacier Intelligence Explorer",
            "How fast is Siachen Glacier moving — and is it changing?",
            [IMG / "app_05_3d_relief.png"],
            ORANGE,
            4.2,
        ),
        make_scene(
            2,
            "The challenge",
            "Remote, dangerous, cloud-covered terrain makes direct monitoring difficult.",
            [IMG / "app_01_globe_intro.png"],
            ORANGE,
            4.0,
        ),
        make_scene(
            3,
            "The NASA-data solution",
            "NISAR shows current seasonal motion. ITS_LIVE provides the historical baseline.",
            [IMG / "app_02_main_view.png"],
            ICE,
            4.0,
        ),
        make_scene(
            4,
            "Transparent science",
            "Radar offsets are cleaned, calibrated, inverted, and checked against independent data.",
            [IMG / "app_06_methodology.png"],
            GREEN,
            4.2,
        ),
        make_scene(
            5,
            "What we discovered",
            "Summer fast ice is about 44% faster; 21.2% of the glacier significantly sped up.",
            [FIG / "nisar_summer_minus_winter.png", FIG / "its_live_change_and_trend.png"],
            ORANGE,
            4.5,
        ),
        make_scene(
            6,
            "A product anyone can explore",
            "Click points, compare seasons, inspect hotspots, and see uncertainty without GIS software.",
            [IMG / "app_03_point_chart.png", IMG / "app_04_profile.png"],
            ICE,
            4.2,
        ),
        make_scene(
            7,
            "Make hidden glacier change visible",
            "Explore the live application: basit6117.github.io/pakistan-glacier-intelligence-explorer/",
            [IMG / "app_07_responsive.png"],
            GREEN,
            4.9,
        ),
    ]

    durations = []
    for index, (scene, duration) in enumerate(scenes, 1):
        frame_path = FRAME_DIR / f"frame_{index:03d}.png"
        scene.save(frame_path, optimize=True)
        durations.append(duration)

    concat_path = FRAME_DIR / "concat.txt"
    with concat_path.open("w", encoding="utf-8") as handle:
        for index, duration in enumerate(durations, 1):
            handle.write(f"file 'frame_{index:03d}.png'\n")
            handle.write(f"duration {duration}\n")
        handle.write(f"file 'frame_{len(durations):03d}.png'\n")

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to encode the demonstration video")
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_path),
            "-vf", "format=yuv420p",
            "-r", "30",
            "-t", "29.8",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(OUT),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(OUT)


if __name__ == "__main__":
    main()
