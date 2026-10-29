"""Uygulama ikonunu (src/ceyrek_tracker/assets/icon.ico) üretir.

İkon elle çizilmiş bir dosya değil, bu betiğin çıktısıdır; değiştirmek için
betiği düzenleyip yeniden çalıştırın:

    python tools/make_icon.py

Tasarım: üstten ışık alan altın bir sikke, kenarında ince bir halka ve ortasında
"¼" (çeyrek). Büyük boyutta çizilip her ikon boyutuna yumuşatılarak küçültülür.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "src" / "ceyrek_tracker" / "assets" / "icon.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]
CANVAS = 1024

GOLD_LIGHT = (250, 222, 134)
GOLD_MID = (227, 185, 80)
GOLD_DARK = (168, 124, 38)
RIM = (122, 88, 24)
GLYPH = (74, 52, 14)

FONT_CANDIDATES = [
    "C:/Windows/Fonts/bahnschrift.ttf",
    "C:/Windows/Fonts/seguisb.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, ...]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b, strict=True))


def _font(size: int) -> ImageFont.ImageFont:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).exists():
            font = ImageFont.truetype(candidate, size)
            if candidate.endswith("bahnschrift.ttf"):
                font.set_variation_by_name("Bold")
            return font
    return ImageFont.load_default(size)


def draw_coin() -> Image.Image:
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 40
    box = (margin, margin, CANVAS - margin, CANVAS - margin)

    # Kenar halkası
    draw.ellipse(box, fill=RIM)

    # Yüz: üst-sol açık, alt-sağ koyu; iç içe dairelerle yumuşak geçiş.
    inset = 46
    steps = 120
    for i in range(steps):
        t = i / (steps - 1)
        color = _lerp(GOLD_DARK, GOLD_LIGHT, t) if t < 0.5 else _lerp(GOLD_MID, GOLD_LIGHT, t)
        shrink = inset + t * 300
        shift = t * 70  # ışık kaynağı sol üstte
        draw.ellipse(
            (
                box[0] + shrink - shift,
                box[1] + shrink - shift,
                box[2] - shrink - shift * 0.2,
                box[3] - shrink - shift * 0.2,
            ),
            fill=color,
        )

    # İnce iç halka
    ring = inset + 34
    draw.ellipse(
        (box[0] + ring, box[1] + ring, box[2] - ring, box[3] - ring),
        outline=(*GOLD_DARK, 200),
        width=14,
    )

    # Ortadaki ¼
    font = _font(560)
    draw.text((CANVAS / 2, CANVAS / 2 + 10), "¼", font=font, fill=GLYPH, anchor="mm")
    return img.filter(ImageFilter.SMOOTH_MORE)


def main() -> None:
    coin = draw_coin()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    coin.resize((256, 256), Image.LANCZOS).save(OUTPUT, format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"{OUTPUT.relative_to(ROOT)} yazıldı ({', '.join(map(str, SIZES))} px)")


if __name__ == "__main__":
    main()
