"""Sağ kenardan kayarak açılan çerçevesiz panel penceresi.

Panel ekran kenarlarına yapışmaz: üst, alt ve sağdan küçük bir boşlukla, yuvarlak
köşeli yüzen bir kart gibi durur. Pencerenin kendisi görünen kartın boyutundadır; zemin ve
köşeler `PanelSurface` tarafından çizilir.

Kayma animasyonu pencereyi hareket ettirmez, *görünen genişliği* (`reveal`) büyütür:
pencerenin sağ kenarı sabit kalır, içerik ise sabit boyutta ve sağa yaslı durur.
Böylece panel, sağda başka bir monitör varsa onun üzerine taşmaz.
"""

from __future__ import annotations

from PySide6.QtCore import Property as QtProperty
from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QRect,
    Qt,
    Signal,
)
from PySide6.QtGui import QGuiApplication, QScreen
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ceyrek_tracker.core.card_host import CardHost
from ceyrek_tracker.core.header import HeaderBar
from ceyrek_tracker.core.panel_surface import PanelSurface
from ceyrek_tracker.core.settings import Settings
from ceyrek_tracker.core.widgets import AutoHideScrollArea
from ceyrek_tracker.theme import Look

PANEL_MARGIN = 8  # kartın ekran kenarlarından uzaklığı (mantıksal px, yoğunlukla ölçeklenir)


class PanelWindow(QWidget):
    shown = Signal()
    hidden = Signal()
    pin_clicked = Signal()

    def __init__(self, look: Look, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Durum paneli")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # görev çubuğunda görünmez
            | Qt.WindowType.WindowDoesNotAcceptFocus  # başka uygulamanın odağını çalmaz
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._look = look
        self._settings = settings
        self._open = False
        self._reveal = 1
        self._width = settings.panel_width
        self._height = 600
        self._margin = look.metrics.sp(PANEL_MARGIN)
        self._right = 0  # kartın sağ kenarı (ekran kenarından `_margin` içeride)
        self._top = 0
        self._screen: QScreen | None = None

        self._surface = PanelSurface(look, self)
        sp = look.metrics.sp
        root = QVBoxLayout(self._surface)
        root.setContentsMargins(sp(16), sp(12), sp(10), sp(10))
        root.setSpacing(sp(8))

        self.header = HeaderBar(look)
        self.header.pin_clicked.connect(self.pin_clicked)
        root.addWidget(self.header)

        self._scroll = AutoHideScrollArea()
        inner = QWidget()
        self._column = QVBoxLayout(inner)
        self._column.setContentsMargins(0, 0, sp(8), 0)
        self._column.setSpacing(sp(10))
        self._column.addStretch(1)
        self._scroll.setWidget(inner)
        root.addWidget(self._scroll, 1)

        self._anim = QPropertyAnimation(self, b"reveal", self)
        self._anim.finished.connect(self._on_anim_finished)

        self.setStyleSheet(look.stylesheet)
        self._set_reveal(1)

    # --- Animasyon özelliği -------------------------------------------------

    def _get_reveal(self) -> int:
        return self._reveal

    def _set_reveal(self, value: int) -> None:
        self._reveal = max(1, int(value))
        self.setGeometry(self._right - self._reveal, self._top, self._reveal, self._height)
        self._surface.move(self._reveal - self._width, 0)

    reveal = QtProperty(int, _get_reveal, _set_reveal)

    # --- Dış arayüz ---------------------------------------------------------

    @property
    def is_open(self) -> bool:
        return self._open

    def target_rect(self) -> QRect:
        """Panelin tamamen açık haldeki etkileşim alanı (animasyondan bağımsız).

        Kartın etrafındaki boşluğu da kapsar: fare ekran kenarına kaydığında panelden
        çıkmış sayılmaz.
        """
        left = self._right - self._width
        return QRect(
            left,
            self._top - self._margin,
            self._width + self._margin,
            self._height + 2 * self._margin,
        )

    def add_host(self, host: CardHost) -> None:
        self._column.insertWidget(self._column.count() - 1, host)

    def set_pinned(self, pinned: bool) -> None:
        self.header.set_pinned(pinned)

    def set_look(self, look: Look) -> None:
        self._look = look
        self.setStyleSheet(look.stylesheet)
        self._surface.set_look(look)

    def open_on(self, screen: QScreen) -> None:
        work = screen.availableGeometry()
        self._screen = screen
        # Yazı ölçeği büyüdükçe panel de orantılı genişler.
        self._width = round(self._settings.panel_width * max(1.0, self._look.metrics.font))
        self._margin = self._look.metrics.sp(PANEL_MARGIN)
        self._height = work.height() - 2 * self._margin
        self._right = work.x() + work.width() - self._margin
        self._top = work.y() + self._margin
        self._surface.setFixedSize(self._width, self._height)

        was_open = self._open
        self._open = True
        self._anim.stop()
        if not was_open:
            self._set_reveal(1)
            self.show()
            self.header.start()
        animate = self._settings.animations and not was_open
        if animate:
            self._start_animation(self._width, QEasingCurve.Type.OutCubic)
        else:
            self._set_reveal(self._width)
            self.shown.emit()

    def close_panel(self) -> None:
        if not self._open:
            return
        self._open = False
        self.header.stop()
        if self._settings.animations and self.isVisible():
            self._start_animation(1, QEasingCurve.Type.InCubic)
        else:
            self.hide()
            self.hidden.emit()

    # --- İç işleyiş ---------------------------------------------------------

    def _start_animation(self, end: int, curve: QEasingCurve.Type) -> None:
        self._anim.stop()
        self._anim.setDuration(self._settings.animation_ms)
        self._anim.setEasingCurve(curve)
        self._anim.setStartValue(self._reveal)
        self._anim.setEndValue(end)
        self._anim.start()

    def _on_anim_finished(self) -> None:
        if self._open:
            self.shown.emit()
        else:
            self.hide()
            self.hidden.emit()

    def screen_of_panel(self) -> QScreen:
        return self._screen or QGuiApplication.primaryScreen()
