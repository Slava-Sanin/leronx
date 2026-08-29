"""Fallback title cards when stock footage is unavailable."""
from __future__ import annotations
import logging
import textwrap
from pathlib import Path

logger = logging.getLogger("leronx.assets")

PALETTES = [
    ((8, 16, 36), (28, 64, 120), (120, 200, 255)),
    ((20, 8, 28), (88, 28, 72), (255, 176, 120)),
    ((6, 24, 22), (12, 80, 64), (160, 240, 200)),
    ((28, 12, 8), (96, 40, 16), (255, 196, 96)),
    ((16, 12, 32), (48, 32, 96), (200, 180, 255)),
]


def _font_path() -> Path | None:
    candidates = [
        Path(r"C:\Windows\Fonts\segoeui.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/System/Library/Fonts/SFNS.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]):
    from PIL import Image

    width, height = size
    strip = Image.new("RGB", (1, height))
    pixels = strip.load()
    for y in range(height):
        t = y / max(height - 1, 1)
        pixels[0, y] = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
    return strip.resize((width, height))


def _draw_wrapped(draw, text: str, font, fill, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    max_width = x1 - x0
    # Estimate characters per line from font size.
    size = getattr(font, "size", 42) or 42
    width_chars = max(12, int(max_width / (size * 0.52)))
    lines = []
    for paragraph in text.split("\n"):
        lines.extend(textwrap.wrap(paragraph, width=width_chars) or [""])
    lines = [line for line in lines if line][:8]
    line_h = int(size * 1.28)
    total_h = line_h * len(lines)
    y = y0 + max(0, (y1 - y0 - total_h) // 2)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        x = x0 + max(0, (max_width - tw) // 2)
        draw.text((x, y), line, font=font, fill=fill)
        y += line_h


def render_title_card(
    text: str,
    output_path: Path,
    resolution: tuple[int, int] = (1920, 1080),
    index: int = 0,
    kicker: str = "",
) -> Path:
    """Write a cinematic title card PNG for a scene."""
    from PIL import Image, ImageDraw, ImageFont, ImageFilter

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = resolution
    top, bottom, accent = PALETTES[index % len(PALETTES)]
    image = _gradient((width, height), top, bottom)

    # Soft accent glow in the lower third.
    glow = Image.new("RGB", (width, height), bottom)
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        (-width * 0.2, height * 0.45, width * 1.2, height * 1.4),
        fill=accent,
    )
    glow = glow.filter(ImageFilter.GaussianBlur(radius=min(width, height) // 8))
    image = Image.blend(image, glow, 0.22)

    draw = ImageDraw.Draw(image)
    font_file = _font_path()
    title_size = max(36, width // 28)
    kicker_size = max(20, width // 48)
    if font_file:
        title_font = ImageFont.truetype(str(font_file), title_size)
        kicker_font = ImageFont.truetype(str(font_file), kicker_size)
    else:
        title_font = ImageFont.load_default()
        kicker_font = title_font

    margin_x = int(width * 0.1)
    if kicker:
        draw.text(
            (margin_x, int(height * 0.22)),
            kicker.upper(),
            font=kicker_font,
            fill=(accent[0], accent[1], accent[2]),
        )
    spoken = text.strip() or "LeronX"
    _draw_wrapped(
        draw,
        spoken,
        title_font,
        (240, 244, 250),
        (margin_x, int(height * 0.32), width - margin_x, int(height * 0.78)),
    )
    bar_y = int(height * 0.86)
    draw.rectangle((margin_x, bar_y, margin_x + int(width * 0.18), bar_y + 6), fill=accent)
    image.save(output_path, format="PNG")
    logger.debug("Title card written: %s", output_path)
    return output_path
