import pytest
from PySide6.QtCore import QBuffer, QByteArray, QEvent, QIODevice, QPoint, QPointF, Qt
from PySide6.QtGui import QColor, QEnterEvent, QImage, QPainter
from PySide6.QtWidgets import QApplication

from ceyrek_tracker.cards.spotify.widgets import (
    CoverView,
    JumpSlider,
    art_rect,
)
from ceyrek_tracker.theme import resolve_look

LOOK = resolve_look("dark", "normal", 1.0)


def _png() -> bytes:
    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(QColor("#336699"))
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


def _spotify_thumbnail() -> QImage:
    """Spotify'ın görseli: şeffaf yanlar, ortada kare kapak, altında logolu siyah bant."""
    image = QImage(300, 300, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.fillRect(34, 1, 233, 233, QColor("#cc8844"))
    painter.fillRect(34, 234, 233, 66, QColor("#000000"))
    painter.fillRect(60, 250, 80, 30, QColor("#ffffff"))  # logo
    painter.end()
    return image


def _png_of(image: QImage) -> bytes:
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


def test_art_rect_finds_the_square_cover_without_logo_band():
    rect = art_rect(_spotify_thumbnail())
    assert (rect.x(), rect.y(), rect.width(), rect.height()) == (34, 1, 233, 233)


def test_art_rect_ignores_images_without_transparent_sides():
    plain = QImage(300, 300, QImage.Format.Format_ARGB32)
    plain.fill(QColor("#336699"))
    assert art_rect(plain) is None
    assert art_rect(QImage(8, 8, QImage.Format.Format_RGB32)) is None


def test_cover_view_shows_only_the_cover_of_spotify_thumbnails(qtbot):
    cover = CoverView(48, LOOK)
    qtbot.addWidget(cover)
    cover.set_cover(_png_of(_spotify_thumbnail()))
    assert (cover._source.width(), cover._source.height()) == (233, 233)


@pytest.fixture
def slider(qtbot):
    slider = JumpSlider("seek")
    slider.setRange(0, 100)
    slider.resize(200, 14)
    qtbot.addWidget(slider)
    slider.show()
    return slider


def test_click_jumps_to_the_clicked_position_and_commits_once(qtbot, slider):
    committed = []
    slider.committed.connect(committed.append)
    qtbot.mouseClick(slider, Qt.MouseButton.LeftButton, pos=QPoint(100, 7))
    assert len(committed) == 1
    assert 48 <= committed[0] <= 52
    assert slider.value() == committed[0]
    assert not slider.isSliderDown()


def test_drag_commits_only_on_release(qtbot, slider):
    committed = []
    slider.committed.connect(committed.append)
    qtbot.mousePress(slider, Qt.MouseButton.LeftButton, pos=QPoint(20, 7))
    qtbot.mouseMove(slider, QPoint(150, 7))
    assert committed == []
    assert slider.isSliderDown()
    qtbot.mouseRelease(slider, Qt.MouseButton.LeftButton, pos=QPoint(150, 7))
    assert len(committed) == 1
    assert 70 <= committed[0] <= 80


def test_cover_view_accepts_image_and_ignores_garbage(qtbot):
    cover = CoverView(72, LOOK)
    qtbot.addWidget(cover)
    cover.set_cover(_png())
    assert cover._source is not None
    cover.grab()  # çizim hatasız çalışır
    cover.set_cover(b"bu bir resim degil")
    assert cover._source is None
    cover.set_cover(None)
    assert cover._source is None
    cover.grab()


def _enter(widget):
    point = QPointF(5, 5)
    QApplication.sendEvent(widget, QEnterEvent(point, point, point))


def _leave(widget):
    QApplication.sendEvent(widget, QEvent(QEvent.Type.Leave))


def test_handle_is_visible_only_while_hovering(slider):
    _leave(slider)  # ekransız ortamda sahte imleç pencerenin köşesinde durabilir
    assert slider.property("hovered") is False
    _enter(slider)
    assert slider.property("hovered") is True
    _leave(slider)
    assert slider.property("hovered") is False


def test_handle_stays_while_dragging_even_if_mouse_leaves(qtbot, slider):
    _enter(slider)
    qtbot.mousePress(slider, Qt.MouseButton.LeftButton, pos=QPoint(20, 7))
    _leave(slider)
    assert slider.property("hovered") is True
    qtbot.mouseRelease(slider, Qt.MouseButton.LeftButton, pos=QPoint(20, 7))
    assert slider.property("hovered") is False


def test_disabled_slider_never_shows_handle(slider):
    _enter(slider)
    slider.setEnabled(False)
    assert slider.property("hovered") is False
    _enter(slider)
    assert slider.property("hovered") is False
