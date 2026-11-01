"""Panelde ortak kullanılan küçük widget yardımcıları."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QMouseEvent, QResizeEvent
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QSizePolicy, QWidget


def repolish(widget: QWidget) -> None:
    """Dinamik özellik (property) değişince stil sayfasının yeniden uygulanmasını sağlar."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()


def make_label(text: str = "", role: str | None = None, wrap: bool = False) -> QLabel:
    """`role`, stil sayfasındaki `QLabel[role="..."]` kuralını seçer."""
    label = QLabel(text)
    if role:
        label.setProperty("role", role)
    label.setWordWrap(wrap)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    return label


def make_frame(role: str) -> QFrame:
    frame = QFrame()
    frame.setProperty("role", role)
    return frame


class ClickableFrame(QFrame):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class ClickableLabel(QLabel):
    """Tıklamayı kendisi yakalar; üstündeki tıklanabilir çerçeveye (ör. kart başlığı) geçmez."""

    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class AutoHideScrollArea(QScrollArea):
    """Kaydırma çubuğu yalnızca fare üzerindeyken görünür (stil sayfasındaki `hover`).

    Çubuğun yeri her zaman ayrılır (içerik sığsa da): "gerektiğinde" göstermek, içerik
    görünür alanı aştığı an görünür genişliği çubuk kadar daraltıp kartları zıplatırdı.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setProperty("hover", False)

    def _set_hover(self, value: bool) -> None:
        if self.property("hover") != value:
            self.setProperty("hover", value)
            repolish(self)

    def enterEvent(self, event: QEvent) -> None:
        self._set_hover(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._set_hover(False)
        super().leaveEvent(event)


class ElidedLabel(QLabel):
    """Sığmayan metni '…' ile kısaltır; kart genişliğini uzun şarkı adlarıyla şişirmez."""

    def __init__(self, role: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        if role:
            self.setProperty("role", role)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._full = ""

    def set_full_text(self, text: str) -> None:
        self._full = text
        self._elide()

    def full_text(self) -> str:
        return self._full

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._elide()

    def _elide(self) -> None:
        shown = self.fontMetrics().elidedText(
            self._full, Qt.TextElideMode.ElideRight, max(0, self.width())
        )
        self.setText(shown)
        self.setToolTip(self._full if shown != self._full else "")
