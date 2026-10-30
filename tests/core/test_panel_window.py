import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QImage, QPixmap, QRegion
from PySide6.QtWidgets import QWidget

from ceyrek_tracker.core.panel_window import PanelWindow
from ceyrek_tracker.core.settings import Settings
from ceyrek_tracker.theme import resolve_look

LOOK = resolve_look("dark", "normal", 1.0)


@pytest.fixture
def surface(qtbot):
    """Boyutu verilmiş, bulanık arka planı (düz kırmızı) takılmış panel yüzeyi."""
    panel = PanelWindow(LOOK, Settings(animations=False))
    qtbot.addWidget(panel)
    surface = panel._surface
    surface.setFixedSize(200, 120)
    backdrop = QPixmap(200, 120)
    backdrop.fill(QColor("#e02020"))
    surface.backdrop = backdrop
    surface.owner = panel  # panel çöp toplanıp yüzeyi yok etmesin
    return surface


def _render(surface) -> QImage:
    image = QImage(surface.size(), QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)
    # DrawWindowBackground olmadan: gerçek panelde de pencere arka planı boyanmaz (saydam).
    surface.render(image, QPoint(0, 0), QRegion(), QWidget.RenderFlag.DrawChildren)
    return image


def test_corners_are_cut_by_an_antialiased_rounded_outline(surface):
    image = _render(surface)
    radius = surface.radius
    assert radius > 0
    # Dikdörtgenin en uç köşesi tamamen saydam: arkadaki pencere görünür.
    for x, y in ((0, 0), (199, 0), (0, 119), (199, 119)):
        assert image.pixelColor(x, y).alpha() == 0, (x, y)
    # Yay boyunca kenar pikselleri yarı saydam (antialiasing), pürüz yok.
    arc_alphas = {image.pixelColor(i, i).alpha() for i in range(radius)}
    assert any(0 < a < 255 for a in arc_alphas)
    # Köşe kesilmiş ama kenarın ortası ve iç kısım tam dolu.
    assert image.pixelColor(8, 60).alpha() == 255
    assert image.pixelColor(radius, 0).alpha() > 0
    assert image.pixelColor(0, radius).alpha() > 0


def test_inside_the_outline_is_opaque_so_clicks_never_fall_through(surface):
    # Windows, alfa değeri 0 olan katmanlı pencere piksellerinde tıklamayı alttaki uygulamaya
    # geçirir; şeklin içindeki her piksel dolu olmalı.
    image = _render(surface)
    inset = surface.radius
    holes = [
        (x, y)
        for y in range(inset, 120 - inset)
        for x in range(1, 199)
        if image.pixelColor(x, y).alpha() != 255
    ]
    assert not holes[:5]


def test_blurred_backdrop_is_drawn_under_the_dark_layer(surface):
    center = _render(surface).pixelColor(8, 60)
    layer = surface.fill
    assert layer is not None and 0 < layer.alpha() < 255
    # Kırmızı arka plan koyu tabakanın altından hafifçe sezilir.
    assert center.red() > layer.red()
    assert center.red() > center.green() + 10


def test_without_backdrop_the_layer_stays_translucent(surface):
    surface.backdrop = None
    center = _render(surface).pixelColor(8, 60)
    assert center.alpha() == surface.fill.alpha() < 255
