import pytest
from PySide6.QtGui import QImage

from ceyrek_tracker.core.panel_surface import PanelSurface, render_surface
from ceyrek_tracker.theme import resolve_look
from ceyrek_tracker.theme.tokens import DARK, LIGHT, contrast_ratio, parse_hex

W, H = 300, 600


def _image(theme, width=W, height=H) -> QImage:
    return render_surface(theme, width, height).toImage()


def _over(image, x, y, backdrop):
    """(x, y) pikselinin `backdrop` renginin üstündeki görünen rengi (hex)."""
    pixel = image.pixelColor(x, y)
    alpha = pixel.alpha() / 255
    mixed = (
        round(channel * alpha + back * (1 - alpha))
        for channel, back in zip(
            (pixel.red(), pixel.green(), pixel.blue()), parse_hex(backdrop), strict=True
        )
    )
    return "#{:02x}{:02x}{:02x}".format(*mixed)


@pytest.mark.parametrize("theme", [DARK, LIGHT])
def test_corners_are_cut_by_an_antialiased_rounded_outline(theme, qapp):
    image = _image(theme)
    for x, y in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)):
        assert image.pixelColor(x, y).alpha() == 0, (x, y)
    radius = theme.radius_panel
    arc = {image.pixelColor(i, i).alpha() for i in range(radius)}
    assert any(0 < alpha < 255 for alpha in arc)  # pürüzsüz (antialiased) yay
    assert image.pixelColor(radius, 0).alpha() > 0  # kenarın düz kısmı başlıyor
    assert image.pixelColor(W // 2, H // 2).alpha() > 0


@pytest.mark.parametrize("theme", [DARK, LIGHT])
def test_every_pixel_inside_the_shape_is_painted_so_clicks_never_fall_through(theme, qapp):
    # Windows, alfa değeri 0 olan katmanlı pencere pikselinde tıklamayı alttaki uygulamaya
    # geçirir; şeklin içi boş piksel içermemeli.
    image = _image(theme)
    inset = theme.radius_panel
    floor = round(theme.glass_opacity * 255) - 4
    holes = [
        (x, y)
        for y in range(inset, H - inset, 7)
        for x in range(1, W - 1, 5)
        if image.pixelColor(x, y).alpha() < floor
    ]
    assert not holes[:5]


@pytest.mark.parametrize("theme", [DARK, LIGHT])
def test_text_stays_readable_even_over_the_brightest_desktop(theme, qapp):
    image = _image(theme)
    backdrop = "#b8b266" if theme is DARK else "#fffaf0"
    worst = {"text": 99.0, "text_soft": 99.0, "text_dim": 99.0}
    inset = theme.radius_panel  # kesilen köşelerde zemin yok, arkadaki masaüstü görünür
    for y in range(inset, H - inset, 3):
        for x in range(inset, W - inset, 2):
            color = _over(image, x, y, backdrop)
            for name in worst:
                worst[name] = min(worst[name], contrast_ratio(getattr(theme, name), color))
    assert worst["text"] >= 7 and worst["text_soft"] >= 4.5, (theme.name, worst)
    assert worst["text_dim"] >= 4.5, (theme.name, worst)


def test_surface_is_lit_from_the_top_in_the_dark_theme(qapp):
    image = _image(DARK)
    top = image.pixelColor(W // 2, 6)
    bottom = image.pixelColor(W // 2, H - 40)
    assert top.lightness() > bottom.lightness()


def test_texture_is_deterministic(qapp):
    assert _image(DARK, 200, 300) == _image(DARK, 200, 300)


def test_tiny_surface_does_not_fail(qapp):
    assert render_surface(DARK, 2, 2).width() == 2


def test_surface_widget_caches_and_follows_the_look(qtbot, monkeypatch):
    from ceyrek_tracker.core import panel_surface

    calls = []
    real = panel_surface.render_surface
    monkeypatch.setattr(
        panel_surface, "render_surface", lambda *args: calls.append(args) or real(*args)
    )
    surface = PanelSurface(resolve_look("dark", "normal", 1.0))
    qtbot.addWidget(surface)
    surface.resize(200, 100)
    surface.show()
    surface.grab()
    surface.grab()
    assert len(calls) == 1  # tekrar çizimde yeniden üretilmez
    surface.set_look(resolve_look("light", "normal", 1.0))
    surface.grab()
    assert len(calls) == 2
