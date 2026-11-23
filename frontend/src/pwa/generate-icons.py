"""Rebuild public PWA icons: python src/pwa/generate-icons.py (Pillow required)."""
from pathlib import Path

from PIL import Image, ImageDraw

OUTPUT = Path(__file__).resolve().parents[2] / "public" / "pwa"
OUTPUT.mkdir(parents=True, exist_ok=True)
SCALE = 4
image = Image.new("RGB", (512 * SCALE, 512 * SCALE), "#185648")
draw = ImageDraw.Draw(image)


def points(values):
    return [(x * SCALE, y * SCALE) for x, y in values]


draw.polygon(points([(145, 183), (207, 173), (250, 193), (250, 337), (207, 317), (145, 328)]), fill="#ffffff")
draw.polygon(points([(367, 183), (305, 173), (262, 193), (262, 337), (305, 317), (367, 328)]), fill="#dfede3")
draw.line(points([(170, 214), (204, 208), (227, 219)]), fill="#98bca6", width=5 * SCALE)
draw.line(points([(170, 246), (204, 240), (227, 251)]), fill="#98bca6", width=5 * SCALE)
draw.line(points([(285, 219), (308, 208), (342, 214)]), fill="#98bca6", width=5 * SCALE)
draw.line(points([(285, 251), (308, 240), (342, 246)]), fill="#98bca6", width=5 * SCALE)
draw.rounded_rectangle((225 * SCALE, 352 * SCALE, 287 * SCALE, 362 * SCALE), radius=5 * SCALE, fill="#d6b16c")
for filename, size in [("icon-192.png", 192), ("icon-512.png", 512), ("icon-maskable-512.png", 512)]:
    image.resize((size, size), Image.Resampling.LANCZOS).save(OUTPUT / filename, optimize=True)
