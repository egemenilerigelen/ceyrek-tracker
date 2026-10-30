"""Sağ kenarda dikey ortada duran ince tutamaç (pill).

Yalnızca tutamacın kendi alanı fareyi yakalar; ekranın geri kalan sağ kenarı (ör.
maksimize bir pencerenin kaydırma çubuğu) etkilenmez. Tamamen olay tabanlıdır.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QRectF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QScreen
from PySide6.QtWidgets import QWidget

from ceyrek_tracker.core.settings import Settings
from ceyrek_tracker.core.trigger.base import Trigger
from ceyrek_tracker.theme import Look


class _HandleWidget(QWidget):
    def __init__(self, owner: HandleTrigger) -> None:
        super().__init__()
        self._owner = owner
        self._hover = False
        self._color = QColor("#cdc072")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def enterEvent(self, event: QEvent) -> None:
        self._hover = True
        self.update()
        self._owner.hovered.emit(self._owner.screen, True)

    def leaveEvent(self, event: QEvent) -> None:
        self._hover = False
        self.update()
        self._owner.hovered.emit(self._owner.screen, False)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._owner.activated.emit(self._owner.screen)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(self._color)
        color.setAlphaF(0.9 if self._hover else 0.45)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        radius = self.width()
        # Sağ kenara yapışık görünsün diye pill genişletilip sağ yarısı kırpılır.
        painter.drawRoundedRect(QRectF(0, 0, self.width() + radius, self.height()), radius, radius)


class HandleTrigger(Trigger):
    def __init__(self) -> None:
        super().__init__()
        self._widget = _HandleWidget(self)
        self.screen: QScreen | None = None
        self._thickness = 6
        self._length = 96
        self._position = 0.5

    def configure(self, settings: Settings, look: Look) -> None:
        self._thickness = settings.handle_thickness
        self._length = settings.handle_length
        self._position = settings.handle_position
        self._widget.set_color(QColor(look.theme.accent))
        if self.screen is not None and self._widget.isVisible():
            self._place(self.screen)

    def show_on(self, screen: QScreen) -> None:
        self.screen = screen
        self._place(screen)
        self._widget.show()

    def hide(self) -> None:
        self._widget.hide()

    def _place(self, screen: QScreen) -> None:
        work = screen.availableGeometry()
        full = screen.geometry()
        length = min(self._length, work.height())
        y = work.top() + round((work.height() - length) * self._position)
        self._widget.setGeometry(
            full.x() + full.width() - self._thickness, y, self._thickness, length
        )

    def shutdown(self) -> None:
        self._widget.hide()
        self._widget.deleteLater()
