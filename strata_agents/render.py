"""Draws the team's file, with or without a candidate asset in place, as PNGs for ASI:One cards.

Everything is drawn with Pillow primitives at 2x and downsampled, so no browser or SVG
library is needed on the agent host.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import PACKAGE_DIR, PREVIEW_DIR

S = 2  # supersampling factor

NAVY = (20, 37, 74)
NAVY_ART = (31, 58, 95)
MINT = (47, 209, 139)
MINT_SOFT = (227, 248, 238)
SAGE = (185, 203, 180)
SAGE_LIGHT = (228, 236, 223)
GREY_LINE = (201, 206, 214)
GREY_SUB = (74, 85, 104)
WHITE = (255, 255, 255)
AI_BLUE = (106, 144, 184)
HIGHLIGHT = (217, 196, 73)
AMBER = (233, 184, 114)
CORAL = (196, 85, 59)

FONT_DIR = PACKAGE_DIR / "assets" / "fonts"


@lru_cache(maxsize=32)
def _font(family: str, size: int, weight: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = FONT_DIR / ("Bricolage.ttf" if family == "display" else "PlusJakarta.ttf")
    try:
        font = ImageFont.truetype(str(path), size)
        axes = font.get_variation_axes()
        values = []
        for axis in axes:
            name = axis.get("name", b"")
            name = name.decode() if isinstance(name, bytes) else str(name)
            if name.lower().startswith("weight"):
                values.append(weight)
            elif name.lower().startswith("optical"):
                values.append(min(max(size // S, axis["minimum"]), axis["maximum"]))
            else:
                values.append(axis.get("default", axis["minimum"]))
        if values:
            font.set_variation_by_axes(values)
        return font
    except OSError:
        return ImageFont.load_default(size)


def _dashed_rect(draw: ImageDraw.ImageDraw, box, color, width=2 * S, dash=8 * S, gap=6 * S):
    x0, y0, x1, y1 = box
    for (ax, ay, bx, by) in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
        length = max(abs(bx - ax), abs(by - ay))
        steps = int(length // (dash + gap)) + 1
        for i in range(steps):
            start = i * (dash + gap)
            end = min(start + dash, length)
            if start >= length:
                break
            fx = lambda t: ax + (bx - ax) * t / length  # noqa: E731
            fy = lambda t: ay + (by - ay) * t / length  # noqa: E731
            draw.line((fx(start), fy(start), fx(end), fy(end)), fill=color, width=width)


# ---------------------------------------------------------------- assets


def draw_asset(asset_id: str, size: int) -> Image.Image:
    """Return the asset artwork as an RGBA image of `size` x `size` pixels."""
    big = size * S
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = big / 170  # all artwork is designed on a 170-unit grid

    def p(*pts):
        return [v * u for v in pts]

    if asset_id == "seedling-jar":
        d.ellipse(p(23, 143, 147, 157), fill=SAGE)
        d.rounded_rectangle(p(52, 62, 118, 146), radius=14 * u, fill=SAGE_LIGHT, outline=NAVY_ART, width=int(4 * u))
        d.rounded_rectangle(p(48, 50, 122, 64), radius=4 * u, fill=NAVY_ART)
        for cx, cy in ((72, 126), (98, 122), (85, 102)):
            d.ellipse(p(cx - 12, cy - 12, cx + 12, cy + 12), fill=SAGE, outline=NAVY_ART, width=int(3.5 * u))
        d.line(p(85, 50, 85, 22), fill=NAVY_ART, width=int(4.5 * u))
        d.ellipse(p(58, 20, 86, 36), fill=NAVY_ART)
        d.ellipse(p(84, 16, 112, 32), fill=NAVY_ART)
    elif asset_id == "paper-boats":
        d.polygon(p(25, 115, 145, 115, 125, 140, 45, 140), fill=NAVY_ART)
        d.polygon(p(85, 30, 85, 112, 125, 112), fill=SAGE, outline=NAVY_ART)
        d.line(p(85, 30, 85, 115), fill=NAVY_ART, width=int(4 * u))
        for x in range(15, 160, 40):
            d.arc(p(x, 145, x + 40, 160), 180, 360, fill=SAGE, width=int(4 * u))
    elif asset_id == "open-door":
        d.rectangle(p(50, 25, 120, 150), outline=NAVY_ART, width=int(4 * u))
        d.polygon(p(50, 25, 92, 40, 92, 160, 50, 150), fill=NAVY_ART)
        d.ellipse(p(80, 88, 88, 96), fill=SAGE)
        d.line(p(20, 150, 150, 150), fill=SAGE, width=int(4 * u))
    elif asset_id == "sunrise-ledger":
        d.ellipse(p(45, 45, 125, 125), fill=AMBER)
        d.rectangle(p(20, 110, 150, 170), fill=(0, 0, 0, 0))
        d.line(p(20, 112, 150, 112), fill=CORAL, width=int(6 * u))
        d.line(p(40, 132, 130, 132), fill=NAVY_ART, width=int(6 * u))
    elif asset_id == "coin-stack":
        for i, y in enumerate((120, 100, 80, 60)):
            d.ellipse(p(45, y, 125, y + 26), fill=MINT if i % 2 else SAGE_LIGHT, outline=NAVY_ART, width=int(4 * u))
        d.ellipse(p(118, 30, 150, 62), outline=NAVY_ART, width=int(4 * u))
    elif asset_id in ("tiny-coins", "soft-circles"):
        filled = asset_id == "soft-circles"
        for cx in (40, 85, 130):
            d.ellipse(p(cx - 20, 65, cx + 20, 105), fill=MINT if filled else None, outline=NAVY_ART, width=int(5 * u))
    else:
        d.rectangle(p(30, 30, 140, 140), outline=NAVY_ART, width=int(4 * u))
    return img.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- the file


def render_frame(
    heading: str,
    placements: dict[str, str] | None = None,
    try_on: tuple[str, str] | None = None,
    highlight_spot: str | None = None,
    width: int = 960,
) -> Image.Image:
    """Draw the desktop frame of the sample site.

    placements: licensed assets already in the file, by spot id.
    try_on: (spot_id, asset_id) previewed with a watermark.
    highlight_spot: draws the selection outline around one spot.
    """
    placements = dict(placements or {})
    W, H = width * S, int(width * 0.5625) * S
    k = W / (960 * S) * S  # layout unit: 1 design px at 960 wide
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    def r(x0, y0, x1, y1):
        return (x0 * k, y0 * k, x1 * k, y1 * k)

    # nav
    d.text((40 * k, 22 * k), "tally.", font=_font("display", int(26 * k), 800), fill=NAVY)
    nav_font = _font("body", int(15 * k), 500)
    for x, label in ((690, "Savings"), (780, "Cards"), (850, "Pricing")):
        d.text((x * k, 28 * k), label, font=nav_font, fill=GREY_SUB)
    d.line(r(0, 72, 960, 72), fill=(238, 240, 242), width=int(1 * k))

    # hero
    d.rectangle(r(0, 73, 960, 400), fill=MINT_SOFT)
    hfont = _font("display", int(52 * k), 800)
    words, lines, line = heading.split(), [], ""
    for w in words:
        trial = (line + " " + w).strip()
        if d.textlength(trial, font=hfont) > 470 * k and line:
            lines.append(line)
            line = w
        else:
            line = trial
    lines.append(line)
    y = 120
    for ln in lines[:3]:
        d.text((40 * k, y * k), ln, font=hfont, fill=NAVY)
        y += 54
    body = _font("body", int(16 * k), 400)
    d.text((40 * k, (y + 14) * k), "Round-ups, gentle goals and no surprise fees.", font=body, fill=GREY_SUB)
    d.rounded_rectangle(r(40, y + 56, 210, y + 102), radius=23 * k, fill=MINT)
    d.text((62 * k, (y + 67) * k), "Open an account", font=_font("body", int(16 * k), 700), fill=NAVY)

    # hero slot
    slot = (600, 110, 920, 370)
    art = None
    watermark = False
    if try_on and try_on[0] == "hero-art":
        art, watermark = try_on[1], True
    elif "hero-art" in placements:
        art = placements["hero-art"]
    if art:
        d.rounded_rectangle(r(*slot), radius=10 * k, fill=WHITE)
        piece = draw_asset(art, int(230 * k))
        img.paste(piece, (int(645 * k), int(124 * k)), piece)
    else:
        d.rounded_rectangle(r(*slot), radius=10 * k, fill=WHITE)
        _dashed_rect(d, r(*slot), AI_BLUE, width=int(2 * k))
    if watermark:
        _watermark(img, r(*slot), k)

    # feature row
    icons = placements.get("feature-icons", "tiny-coins")
    if try_on and try_on[0] == "feature-icons":
        icons = try_on[1]
    tfont = _font("body", int(15 * k), 700)
    sfont = _font("body", int(13 * k), 400)
    for i, (title, sub) in enumerate((
        ("Round-ups", "Spare change, quietly saved."),
        ("Gentle goals", "Targets that bend with your month."),
        ("No surprise fees", "Every charge, in plain words."),
    )):
        x = 40 + i * 300
        ico = draw_asset(icons, int(44 * k))
        img.paste(ico, (int(x * k), int(424 * k)), ico)
        d.text(((x + 56) * k, 428 * k), title, font=tfont, fill=NAVY)
        d.text(((x + 56) * k, 452 * k), sub, font=sfont, fill=GREY_SUB)
    if try_on and try_on[0] == "feature-icons":
        _watermark(img, r(30, 410, 930, 500), k)

    if highlight_spot:
        box = {"hero-art": slot, "feature-icons": (24, 410, 936, 500)}.get(highlight_spot)
        if box:
            pad = 6
            d.rectangle(r(box[0] - pad, box[1] - pad, box[2] + pad, box[3] + pad), outline=HIGHLIGHT, width=int(3 * k))

    return img.resize((W // S, H // S), Image.LANCZOS)


def render_mobile(heading: str, art: str | None, watermark: bool = False, width: int = 300) -> Image.Image:
    """A phone-sized view of the same hero, for the mobile-hero spot."""
    W, H = width * S, int(width * 1.9) * S
    k = W / 300
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    d.text((20 * k, 18 * k), "tally.", font=_font("display", int(20 * k), 800), fill=NAVY)
    d.rectangle((0, 56 * k, W, 420 * k), fill=MINT_SOFT)
    slot = (40 * k, 76 * k, 260 * k, 266 * k)
    d.rounded_rectangle(slot, radius=10 * k, fill=WHITE)
    if art:
        piece = draw_asset(art, int(170 * k))
        img.paste(piece, (int(65 * k), int(86 * k)), piece)
        if watermark:
            _watermark(img, slot, k)
    else:
        _dashed_rect(d, slot, AI_BLUE, width=int(2 * k))
    hfont = _font("display", int(30 * k), 800)
    d.text((20 * k, 290 * k), "Money that", font=hfont, fill=NAVY)
    d.text((20 * k, 322 * k), "waits for you.", font=hfont, fill=NAVY)
    d.rounded_rectangle((20 * k, 372 * k, 170 * k, 406 * k), radius=17 * k, fill=MINT)
    return img.resize((W // S, H // S), Image.LANCZOS)


def _watermark(img: Image.Image, box, k: float):
    """Diagonal 'PREVIEW · STRATA' text across a box, at low opacity."""
    x0, y0, x1, y1 = (int(v) for v in box)
    w, h = x1 - x0, y1 - y0
    layer = Image.new("RGBA", (w * 2, h * 2), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    font = _font("body", int(16 * k), 700)
    for row in range(0, h * 2, int(46 * k)):
        ld.text((0, row), "PREVIEW · STRATA   " * 6, font=font, fill=NAVY + (60,))
    layer = layer.rotate(24, resample=Image.BICUBIC)
    crop = layer.crop((w // 2, h // 2, w // 2 + w, h // 2 + h))
    img.paste(crop, (x0, y0), crop)


def render_spot_tile(spot_id: str, heading: str, placements: dict[str, str] | None = None) -> Image.Image:
    """Square-ish tile for the element picker: the spot cropped from the real frame."""
    if spot_id == "mobile-hero":
        phone = render_mobile(heading, (placements or {}).get("mobile-hero"))
        phone.thumbnail((150, 284), Image.LANCZOS)
        canvas = Image.new("RGB", (400, 300), (246, 247, 248))
        x, y = (400 - phone.width) // 2, (300 - phone.height) // 2
        canvas.paste(phone, (x, y))
        ImageDraw.Draw(canvas).rounded_rectangle(
            (x - 4, y - 4, x + phone.width + 4, y + phone.height + 4), radius=14, outline=(154, 163, 174), width=2
        )
        return canvas
    frame = render_frame(heading, placements, highlight_spot=spot_id)
    boxes = {"hero-art": (560, 90, 960, 400), "feature-icons": (0, 400, 960, 540)}
    crop = frame.crop(boxes.get(spot_id, (0, 0, 960, 540)))
    canvas = Image.new("RGB", (400, 300), WHITE)
    crop.thumbnail((400, 300), Image.LANCZOS)
    canvas.paste(crop, ((400 - crop.width) // 2, (300 - crop.height) // 2))
    return canvas


# ---------------------------------------------------------------- files


def save_png(img: Image.Image, stem: str) -> str:
    """Save under PREVIEW_DIR with a content hash in the name; returns the file name."""
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    data = img.tobytes()
    digest = hashlib.sha1(data).hexdigest()[:10]
    name = f"{stem}-{digest}.png"
    path: Path = PREVIEW_DIR / name
    if not path.exists():
        img.save(path, "PNG", optimize=True)
    return name
