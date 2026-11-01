import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor, QImage, QRegion, qAlpha, qBlue, qGreen, qRed
from PySide6.QtWidgets import QFrame, QWidget

from ceyrek_tracker.cards.spotify.backdrop import (
    DOT_ALPHA,
    DOT_ALPHA_LIGHT,
    MAX_ALPHA,
    SpotifyBackdrop,
    _halftone,
    render_backdrop,
)
from ceyrek_tracker.cards.spotify.palette import Palette
from ceyrek_tracker.theme import resolve_look

LOOK = resolve_look("dark", "normal", 1.0)
W, H = 276, 135


@pytest.fixture(autouse=True)
def _qt_application(qapp):
    """QPixmap çalışan bir Qt uygulaması ister; test tek başına çalıştırılsa da olsun."""


def _alphas(image: QImage, x0: int, y0: int, x1: int, y1: int) -> list[int]:
    return [qAlpha(image.pixel(x, y)) for y in range(y0, y1, 2) for x in range(x0, x1, 2)]


def _mean(values: list[int]) -> float:
    return sum(values) / len(values)


def test_backdrop_is_visible_but_every_pixel_stays_faint():
    image = render_backdrop(W, H).toImage()
    peak = max(_alphas(image, 0, 0, W, H))
    assert peak > 0
    # Üst üste binen katmanlar bile hiçbir noktada yarım opaklığı geçmez.
    assert peak <= 255 * 0.5
    assert MAX_ALPHA <= 0.2


def _redness(image: QImage, x0: int = 0, y0: int = 0, x1: int = W, y1: int = H) -> float:
    """Nokta deseni renksizdir; bu ölçü yalnızca kapaktan gelen tonu görür."""
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    total = 0
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 2):
            pixel = image.pixel(x, y)
            total += qAlpha(pixel) * (qRed(pixel) - qBlue(pixel))
    return total


RED = Palette("#cc3333", "#cc8833")
BLUE = Palette("#3366cc", "#33aacc")


def test_light_spills_from_the_cover_corner_and_the_far_corner_stays_calm():
    image = render_backdrop(W, H, RED).toImage()
    cover_side = _redness(image, 4, 4, 54, 54)
    far_corner = _redness(image, W - 54, 4, W - 4, 54)
    assert cover_side > far_corner * 1.5 > 0


def test_far_corner_stays_faint_even_where_the_layers_overlap():
    image = render_backdrop(W, H).toImage()
    quiet = _alphas(image, int(W * 0.7), 2, W - 2, int(H * 0.3))
    assert max(quiet) <= 255 * (MAX_ALPHA + DOT_ALPHA)


def test_glow_takes_the_tone_of_the_palette():
    assert _redness(render_backdrop(W, H, RED).toImage()) > 0
    assert _redness(render_backdrop(W, H, BLUE).toImage()) < 0


def _on_panel(frame: QFrame, look) -> QImage:
    """Çerçevenin panelde görünen hâli: önce panel zemini, sonra stil sayfasıyla çerçeve."""
    frame.setStyleSheet(look.stylesheet)
    frame.resize(W, H)
    image = QImage(W, H, QImage.Format.Format_RGB32)
    image.fill(QColor(look.theme.bg))
    frame.render(image, QPoint(), QRegion(), QWidget.RenderFlag.DrawChildren)
    return image


def _distance_from_panel(look, image: QImage) -> float:
    """Kapağın ışığından uzak köşenin panel renginden ortalama farkı."""
    bg = QColor(look.theme.bg)
    gaps = []
    for y in range(4, 40, 2):
        for x in range(W - 60, W - 4, 2):
            pixel = image.pixel(x, y)
            gaps.append(
                abs(qRed(pixel) - bg.red())
                + abs(qGreen(pixel) - bg.green())
                + abs(qBlue(pixel) - bg.blue())
            )
    return _mean(gaps)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_card_sits_on_the_panel_instead_of_floating_above_it(qtbot, theme):
    look = resolve_look(theme, "normal", 1.0)
    sunk = SpotifyBackdrop(look)
    plain = QFrame()
    plain.setProperty("role", "inner")
    qtbot.addWidget(sunk)
    qtbot.addWidget(plain)
    floating = _distance_from_panel(look, _on_panel(plain, look))
    settled = _distance_from_panel(look, _on_panel(sunk, look))
    assert floating > 0
    assert settled < floating / 2


def _dot_alphas(dark: bool) -> list[int]:
    return _alphas(
        _halftone(W, H, 1.0, dark).convertToFormat(QImage.Format.Format_ARGB32), 0, 0, W, H
    )


def test_dots_grow_from_the_cover_corner_towards_the_far_corner():
    image = _halftone(W, H, 1.0, True)
    cover_side = _mean(_alphas(image, 0, 0, 60, 60))
    far_corner = _mean(_alphas(image, W - 60, H - 60, W, H))
    assert far_corner > cover_side * 2


@pytest.mark.parametrize(("dark", "peak"), [(True, DOT_ALPHA), (False, DOT_ALPHA_LIGHT)])
def test_dots_stay_faint_and_leave_gaps_between_them(dark, peak):
    alphas = _dot_alphas(dark)
    assert max(alphas) <= round(255 * peak)
    assert 0 in alphas  # noktalar birleşip düz bir tabakaya dönüşmez


@pytest.mark.parametrize(("dark", "red"), [(True, 0), (False, 255)])
def test_dots_are_painted_against_the_text_so_they_never_reduce_contrast(dark, red):
    image = _halftone(W, H, 1.0, dark).convertToFormat(QImage.Format.Format_ARGB32)
    dots = [
        qRed(image.pixel(x, y))
        for y in range(0, H, 3)
        for x in range(0, W, 3)
        if qAlpha(image.pixel(x, y)) > 20
    ]
    assert dots
    assert all(abs(value - red) <= 3 for value in dots)


def test_song_change_reuses_the_pattern_instead_of_drawing_it_again():
    _halftone.cache_clear()
    render_backdrop(W, H, RED)
    render_backdrop(W, H, BLUE)
    assert _halftone.cache_info().misses == 1


def test_pattern_follows_the_device_pixel_ratio():
    image = _halftone(W, H, 1.5, True)
    assert (image.width(), image.height()) == (round(W * 1.5), round(H * 1.5))
    assert image.devicePixelRatio() == 1.5


def test_palette_change_redraws_the_widget_cache(qtbot):
    frame = SpotifyBackdrop(LOOK)
    qtbot.addWidget(frame)
    frame.resize(W, H)
    frame.show()
    frame.grab()
    assert frame._cache is not None
    frame.set_palette(Palette("#cc3333", "#cc8833"))
    assert frame._cache is None
    frame.grab()
    frame.set_palette(Palette("#cc3333", "#cc8833"))  # aynı palet: yeniden çizmeye gerek yok
    assert frame._cache is not None


def test_same_size_always_gives_the_same_picture():
    first = render_backdrop(W, H).toImage()
    _halftone.cache_clear()
    assert first == render_backdrop(W, H).toImage()


def test_light_theme_glow_is_a_little_fainter_than_dark():
    dark = _redness(render_backdrop(W, H, RED, dark=True).toImage())
    light = _redness(render_backdrop(W, H, RED, dark=False).toImage())
    assert 0 < light < dark


def test_tiny_or_hidden_widget_does_not_crash_and_stays_transparent():
    image = render_backdrop(4, 4).toImage()
    assert max(_alphas(image, 0, 0, 4, 4)) == 0


def test_device_pixel_ratio_scales_the_picture_not_its_logical_size():
    pixmap = render_backdrop(W, H, ratio=2.0)
    assert (pixmap.width(), pixmap.height()) == (W * 2, H * 2)
    assert pixmap.devicePixelRatio() == 2.0


def test_backdrop_widget_paints_over_the_inner_frame(qtbot):
    frame = SpotifyBackdrop(LOOK)
    qtbot.addWidget(frame)
    frame.resize(W, H)
    frame.show()
    assert frame.property("role") == "inner"
    frame.grab()
    assert frame._cache is not None
    frame.resize(W + 10, H)
    assert frame._cache is None  # boyut değişince yeniden çizilir
    frame.set_look(resolve_look("light", "normal", 1.0))
    assert frame._dark is False
