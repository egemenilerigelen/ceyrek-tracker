from PySide6.QtCore import QRect
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap

from ceyrek_tracker.core.backdrop import blur_image, capture_blurred


def _stripes(width=400, height=200) -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    painter = QPainter(image)
    for x in range(0, width, 24):
        painter.fillRect(x, 0, 12, height, QColor("#ffffff"))
        painter.fillRect(x + 12, 0, 12, height, QColor("#e02020"))
    painter.end()
    return image


def _spread(image: QImage) -> int:
    values = [image.pixelColor(60 + i, 100).green() for i in range(240)]
    return max(values) - min(values)


def test_blur_smooths_fine_patterns_but_keeps_size():
    image = _stripes()
    blurred = blur_image(image)
    assert blurred.size() == image.size()
    assert _spread(image) > 200
    assert _spread(blurred) < 40


def test_blur_keeps_average_color():
    flat = QImage(80, 40, QImage.Format.Format_RGB32)
    flat.fill(QColor("#336699"))
    assert blur_image(flat).pixelColor(40, 20) == QColor("#336699")


def test_blur_of_tiny_image_does_not_fail():
    tiny = QImage(1, 1, QImage.Format.Format_RGB32)
    tiny.fill(QColor("#ffffff"))
    assert blur_image(tiny).size() == tiny.size()


class _FakeScreen:
    """`capture_blurred`'in kullandığı QScreen yüzeyi: ekran görüntüsü ve geometri."""

    def __init__(self, ratio, origin=(0, 0)):
        self._ratio = ratio
        self._origin = origin

    def grabWindow(self, _window):
        pixmap = QPixmap(round(400 * self._ratio), round(300 * self._ratio))
        pixmap.fill(QColor("#336699"))
        pixmap.setDevicePixelRatio(self._ratio)
        return pixmap

    def geometry(self):
        return QRect(self._origin[0], self._origin[1], 400, 300)


def test_capture_crops_requested_region_in_physical_pixels():
    result = capture_blurred(_FakeScreen(2.0), QRect(100, 50, 120, 80))
    assert result is not None
    assert (result.width(), result.height()) == (240, 160)
    assert result.devicePixelRatio() == 2.0


def test_capture_is_relative_to_the_screen_origin():
    result = capture_blurred(_FakeScreen(1.0, origin=(1920, 0)), QRect(1920 + 10, 10, 50, 50))
    assert result is not None
    assert (result.width(), result.height()) == (50, 50)


def test_capture_outside_the_screen_returns_none():
    assert capture_blurred(_FakeScreen(1.0), QRect(5000, 5000, 50, 50)) is None
