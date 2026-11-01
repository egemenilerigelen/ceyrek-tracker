"""Spotify kartına özgü widget'lar: tıklanan yere atlayan kaydırıcı, kapak, kısaltan etiket."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPixmap,
    QWheelEvent,
    qAlpha,
)
from PySide6.QtWidgets import QSlider, QStyle, QWidget

from ceyrek_tracker.core.widgets import repolish
from ceyrek_tracker.theme import Look
from ceyrek_tracker.theme.tokens import ICON_FONT

NOTE_GLYPH = ""  # Segoe MDL2 Assets: müzik notu (kapak yokken)


ALPHA_MIN = 16  # bundan şeffaf piksel "boş" sayılır


def art_rect(image: QImage) -> QRect | None:
    """Kapak resminin kendisini bulur; Spotify'ın eklediği logo bandını dışarıda bırakır.

    Spotify kapağı 300x300'lük bir görsele koyar: ortada kare kapak, yanlarda şeffaf şeritler
    ve altında beyaz Spotify logolu siyah bir bant. Yanları şeffaf olmayan görsellerde (başka
    bir kaynak, podcast) `None` döner ve görsel olduğu gibi kullanılır.
    """
    if not image.hasAlphaChannel():
        return None
    image = image.convertToFormat(QImage.Format.Format_ARGB32)
    width, height = image.width(), image.height()
    middle = height // 2

    def opaque(x: int, y: int) -> bool:
        return qAlpha(image.pixel(x, y)) >= ALPHA_MIN

    left = 0
    while left < width and not opaque(left, middle):
        left += 1
    right = width - 1
    while right > left and not opaque(right, middle):
        right -= 1
    side = right - left + 1
    if side >= width or side < height // 2:
        return None  # yanlarda şerit yok ya da beklenen düzen değil
    centre = (left + right) // 2
    top = 0
    while top < height and not opaque(centre, top):
        top += 1
    return QRect(left, top, side, min(side, height - top))


class JumpSlider(QSlider):
    """Çubuğun tıklanan yerine atlayan yatay kaydırıcı (QSlider varsayılanı sayfa kadar kayar).

    `committed(değer)`: kullanıcı bıraktığında bir kez yayınlanır (atlamak için). Sürüklerken
    `valueChanged` yayınlanır ve `isSliderDown()` doğrudur. Tekerlek yok sayılır: panelde
    gezinirken sesin ya da konumun yanlışlıkla değişmemesi için.

    Tutamaç (nokta) yalnızca fare çubuğun üzerindeyken ya da sürüklerken görünür; stil sayfası
    bunu `hovered` özelliğiyle seçer.
    """

    committed = Signal(int)

    def __init__(self, role: str, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setProperty("role", role)
        self.setProperty("hovered", False)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover = False
        self.sliderPressed.connect(self._refresh_handle)
        self.sliderReleased.connect(self._refresh_handle)

    def _refresh_handle(self) -> None:
        shown = self.isEnabled() and (self._hover or self.isSliderDown())
        if self.property("hovered") != shown:
            self.setProperty("hovered", shown)
            repolish(self)

    def enterEvent(self, event: QEvent) -> None:
        self._hover = True
        self._refresh_handle()
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._hover = False
        self._refresh_handle()
        super().leaveEvent(event)

    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.EnabledChange:
            self._refresh_handle()
        super().changeEvent(event)

    def _value_at(self, event: QMouseEvent) -> int:
        return QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), round(event.position().x()), max(1, self.width())
        )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setSliderDown(True)
            self.setValue(self._value_at(event))
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.isSliderDown():
            self.setValue(self._value_at(event))
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isSliderDown():
            self.setValue(self._value_at(event))
            self.setSliderDown(False)
            self.committed.emit(self.value())
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        event.ignore()


class CoverView(QWidget):
    """Yuvarlak köşeli albüm kapağı; kapak yokken sönük bir müzik notu."""

    def __init__(self, size: int, look: Look, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._radius = look.theme.radius_card
        self._source: QPixmap | None = None
        self._scaled: QPixmap | None = None
        self.set_look(look)

    def set_look(self, look: Look) -> None:
        self._fill = QColor(look.theme.ink)
        self._fill.setAlphaF(look.theme.surface_hover_alpha)
        self._glyph = QColor(look.theme.text_dim)
        self._glyph.setAlphaF(0.6)
        self._glyph_size = look.metrics.fs(26)
        self.update()

    def set_cover(self, data: bytes | None) -> None:
        image = QImage.fromData(data) if data else QImage()
        if image.isNull():
            self._source = None
        else:
            if (crop := art_rect(image)) is not None:
                image = image.copy(crop)
            self._source = QPixmap.fromImage(image)
        self._scaled = None
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(self.rect()), self._radius, self._radius)
        p.setClipPath(clip)
        if self._source is None:
            p.fillPath(clip, self._fill)
            font = QFont(ICON_FONT)
            font.setPixelSize(self._glyph_size)
            p.setFont(font)
            p.setPen(self._glyph)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, NOTE_GLYPH)
            return
        if self._scaled is None:
            ratio = self.devicePixelRatioF()
            side = round(self.width() * ratio)
            self._scaled = self._source.scaled(
                side,
                side,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._scaled.setDevicePixelRatio(ratio)
        p.drawPixmap(0, 0, self._scaled)
