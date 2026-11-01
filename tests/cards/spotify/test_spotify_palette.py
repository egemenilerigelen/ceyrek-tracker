import random

import pytest
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QRadialGradient

from ceyrek_tracker.cards.spotify.palette import (
    DEFAULT,
    GLOW_LIGHTNESS,
    MIN_CONTRAST,
    Palette,
    accent_for,
    extract_palette,
    groove_behind_bar,
    oklch,
    to_hex,
)
from ceyrek_tracker.theme.tokens import DARK, LIGHT, blend, contrast_ratio

THEMES = (DARK, LIGHT)


def encode(image: QImage, fmt: str = "PNG", quality: int = -1) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, fmt, quality)
    return bytes(data)


def solid(color: str, size: int = 40) -> QImage:
    image = QImage(size, size, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    return image


def hue(color: str) -> float:
    return oklch(color)[2]


def gap(a: float, b: float) -> float:
    d = abs(a - b) % 360
    return min(d, 360 - d)


def assert_hue(color: str, expected: float, tolerance: float = 10) -> None:
    assert gap(hue(color), expected) <= tolerance, (color, hue(color), expected)


def near_black_with_turquoise() -> QImage:
    """Kahverengimsi koyu gürültü üzerinde küçük, gerçek renk."""
    image = solid("#160d08", 300)
    rng = random.Random(1)
    painter = QPainter(image)
    for _ in range(4000):
        shade = rng.randrange(14, 34)
        painter.fillRect(
            rng.randrange(300), rng.randrange(300), 3, 3, QColor(shade + 8, shade, shade - 8)
        )
    glow = QRadialGradient(QPointF(210, 90), 70)
    glow.setColorAt(0, QColor("#19c8b8"))
    glow.setColorAt(1, QColor(25, 200, 184, 0))
    painter.setBrush(glow)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(QPointF(210, 90), 70, 70)
    painter.end()
    return image


def cream_with_blue() -> QImage:
    image = solid("#f5efe3", 300)
    painter = QPainter(image)
    painter.fillRect(90, 90, 120, 120, QColor("#1f4fd8"))
    painter.end()
    return image


def portrait_with_red_title() -> QImage:
    image = solid("#f0ebe4", 300)
    painter = QPainter(image)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#d8a890"))
    painter.drawEllipse(QPointF(150, 130), 80, 95)
    painter.setBrush(QColor("#2a1d18"))
    painter.drawEllipse(QPointF(150, 70), 85, 50)
    painter.fillRect(30, 262, 240, 26, QColor("#d81e2c"))
    painter.end()
    return image


def spotify_thumbnail(art: QImage) -> QImage:
    """Spotify'ın biçimi: şeffaf yanlar, kare kapak, altta beyaz logolu siyah bant."""
    image = QImage(300, 300, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.drawImage(QRect(34, 1, 233, 233), art)
    painter.fillRect(34, 234, 233, 66, QColor("#000000"))
    painter.fillRect(60, 252, 150, 28, QColor("#ffffff"))
    painter.end()
    return image


def noisy(image: QImage, amount: int = 14) -> QImage:
    rng = random.Random(3)
    out = image.copy()
    for y in range(out.height()):
        for x in range(out.width()):
            c = out.pixelColor(x, y)
            d = rng.randint(-amount, amount)
            out.setPixelColor(
                x, y, QColor(*(min(255, max(0, v + d)) for v in (c.red(), c.green(), c.blue())))
            )
    return out


# --- Renk dönüşümü ---------------------------------------------------------


@pytest.mark.parametrize(
    ("color", "expected"),
    [("#ff0000", (0.628, 0.258, 29.2)), ("#0000ff", (0.452, 0.313, 264.1))],
)
def test_oklch_matches_published_values(color, expected):
    lightness, chroma, degrees = oklch(color)
    assert lightness == pytest.approx(expected[0], abs=0.002)
    assert chroma == pytest.approx(expected[1], abs=0.002)
    assert degrees == pytest.approx(expected[2], abs=0.3)


def test_black_and_white_are_the_ends_of_the_scale():
    assert oklch("#000000")[:2] == pytest.approx((0, 0), abs=0.001)
    assert oklch("#ffffff")[:2] == pytest.approx((1, 0), abs=0.001)


@pytest.mark.parametrize(
    "color", ["#e02020", "#2050e0", "#30b050", "#e0c020", "#8030c0", "#808080"]
)
def test_conversion_round_trip(color):
    assert to_hex(*oklch(color)) == color


@pytest.mark.parametrize("degrees", range(0, 360, 20))
def test_unreachable_colour_loses_only_chroma(degrees):
    color = to_hex(0.8, 0.4, degrees)
    lightness, _, result_hue = oklch(color)
    assert lightness == pytest.approx(0.8, abs=0.015)
    assert gap(result_hue, degrees) <= 4


# --- Doğru rengi seçme -----------------------------------------------------


@pytest.mark.parametrize("degrees", range(0, 360, 5))
def test_every_hue_is_recognised_and_glows_with_equal_strength(degrees):
    """Tüm ton çemberi: dilim sınırı ya da 0/360 geçişi rengi bozmamalı."""
    source = QColor.fromHslF(degrees / 360, 0.85, 0.5).name()
    palette = extract_palette(encode(solid(source)))
    assert_hue(palette.primary, hue(source), 8)
    assert oklch(palette.primary)[0] == pytest.approx(GLOW_LIGHTNESS, abs=0.015)


def test_small_real_colour_beats_dark_brownish_noise():
    assert_hue(extract_palette(encode(near_black_with_turquoise())).primary, hue("#19c8b8"))


def test_cream_paper_does_not_count_as_a_colour():
    assert_hue(extract_palette(encode(cream_with_blue())).primary, hue("#1f4fd8"))


def test_vivid_title_beats_pale_skin_tones():
    assert_hue(extract_palette(encode(portrait_with_red_title())).primary, hue("#d81e2c"))


def test_two_colour_cover_gives_both_colours():
    image = solid("#e02020", 50)
    painter = QPainter(image)
    painter.fillRect(30, 0, 20, 50, QColor("#2050e0"))
    painter.end()
    palette = extract_palette(encode(image))
    assert_hue(palette.primary, hue("#e02020"))
    assert_hue(palette.secondary, hue("#2050e0"))


def test_single_colour_cover_gets_a_neighbouring_second_tone():
    palette = extract_palette(encode(solid("#e02020")))
    assert_hue(palette.secondary, hue(palette.primary) + 28)


def test_black_band_and_white_logo_are_cut_away():
    art = solid("#e08020", 233)
    wrapped = extract_palette(encode(spotify_thumbnail(art)))
    assert wrapped == extract_palette(encode(art))


def test_transparent_sides_are_ignored():
    image = QImage(60, 60, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.fillRect(15, 0, 30, 60, QColor("#2050e0"))
    painter.end()
    assert_hue(extract_palette(encode(image)).primary, hue("#2050e0"))


# --- Renksiz kapaklara renk uydurmama --------------------------------------


@pytest.mark.parametrize("color", ["#807a74", "#7a7f85", "#202020", "#f4f4f4"])
def test_grey_cover_stays_neutral(color):
    palette = extract_palette(encode(solid(color)))
    assert palette.hue is None
    assert palette.primary == palette.secondary
    assert oklch(palette.primary)[1] < 0.01
    for theme in THEMES:
        assert oklch(accent_for(palette, theme))[1] < 0.01


def test_tiny_coloured_speck_does_not_colour_a_black_and_white_cover():
    image = solid("#404040", 300)
    painter = QPainter(image)
    painter.fillRect(140, 140, 20, 20, QColor("#e02020"))
    painter.end()
    assert extract_palette(encode(image)).hue is None


def test_pale_cover_is_not_made_vivid():
    palette = extract_palette(encode(solid("#8d7c6a")))  # sepya
    assert palette.hue is not None
    assert palette.chroma < 0.05
    for theme in THEMES:
        assert oklch(accent_for(palette, theme))[1] <= palette.chroma * 1.3 + 0.01


# --- Kararlılık ------------------------------------------------------------


@pytest.mark.parametrize(
    "make", [near_black_with_turquoise, cream_with_blue, portrait_with_red_title]
)
def test_same_cover_gives_the_same_tone_however_it_is_stored(make):
    art = make()
    base = hue(extract_palette(encode(art)).primary)
    for variant in (
        encode(art, "JPG", 60),
        encode(art, "JPG", 30),
        encode(noisy(art)),
        encode(spotify_thumbnail(art)),
    ):
        assert_hue(extract_palette(variant).primary, base, 10)


def test_result_is_deterministic():
    data = encode(portrait_with_red_title())
    assert extract_palette(data) == extract_palette(data)


@pytest.mark.parametrize("data", [None, b"", b"bu bir resim degil"])
def test_missing_or_broken_cover_uses_the_default(data):
    assert extract_palette(data) == DEFAULT


def test_fully_transparent_cover_uses_the_default():
    image = QImage(20, 20, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    assert extract_palette(encode(image)) == DEFAULT


# --- Çubuk ve düğme rengi --------------------------------------------------


def test_no_accent_without_a_cover_so_the_theme_accent_stays():
    for theme in THEMES:
        assert accent_for(DEFAULT, theme) is None


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.name)
@pytest.mark.parametrize("degrees", range(0, 360, 15))
def test_accent_is_readable_on_the_real_groove_and_keeps_the_hue(theme, degrees):
    source = QColor.fromHslF(degrees / 360, 0.85, 0.5).name()
    palette = extract_palette(encode(solid(source)))
    accent = accent_for(palette, theme)
    assert contrast_ratio(accent, groove_behind_bar(theme, palette.primary)) >= MIN_CONTRAST
    assert_hue(accent, hue(source), 12)


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.name)
@pytest.mark.parametrize("degrees", range(0, 360, 15))
def test_play_icon_stays_readable_on_its_tinted_disc(theme, degrees):
    source = QColor.fromHslF(degrees / 360, 0.85, 0.5).name()
    palette = extract_palette(encode(solid(source)))
    surface = blend(theme.ink, theme.bg, theme.surface_alpha)
    disc = blend(accent_for(palette, theme), surface, 0.38)
    assert contrast_ratio(theme.text, disc) >= 3.0, disc


def test_accent_brightness_does_not_jump_between_songs():
    for theme in THEMES:
        values = [
            oklch(
                accent_for(
                    extract_palette(encode(solid(QColor.fromHslF(d / 360, 0.85, 0.5).name()))),
                    theme,
                )
            )[0]
            for d in range(0, 360, 15)
        ]
        assert max(values) - min(values) <= 0.05, theme.name


def test_accent_uses_the_palette_hue_not_the_clamped_glow():
    vivid = Palette(to_hex(0.62, 0.14, 250), "#000000", 250.0, 0.25)
    pale = Palette(to_hex(0.62, 0.04, 250), "#000000", 250.0, 0.04)
    assert oklch(accent_for(vivid, DARK))[1] > oklch(accent_for(pale, DARK))[1]
