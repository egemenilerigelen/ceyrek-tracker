"""Sağ kenardan kayarak açılan çerçevesiz panel penceresi.

Panel ekran kenarlarına yapışmaz: üst, alt ve sağdan küçük bir boşlukla, yuvarlak
köşeli yüzen bir kart gibi durur. Pencerenin kendisi görünen kartın boyutundadır. Köşeler ve
cam efekti tamamen Qt ile çizilir (bkz. `core/backdrop.py`), bu yüzden köşeler pürüzsüzdür.

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
    QRectF,
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QScreen,
    QTransform,
)
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ceyrek_tracker.core import backdrop
from ceyrek_tracker.core.card_host import CardHost
from ceyrek_tracker.core.header import HeaderBar
from ceyrek_tracker.core.settings import Settings
from ceyrek_tracker.core.widgets import AutoHideScrollArea, make_frame
from ceyrek_tracker.theme import Look
from ceyrek_tracker.theme.tokens import parse_hex

PANEL_MARGIN = 8  # kartın ekran kenarlarından uzaklığı (mantıksal px, yoğunlukla ölçeklenir)


class _Surface(QWidget):
    """Panelin çizilen yüzeyi: yuvarlak köşeli kart, bulanık arka plan, koyu tabaka, kenarlık."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.fill: QColor | None = None  # arka planın (ya da canlı masaüstünün) üstündeki tabaka
        self.backdrop: QPixmap | None = None  # bulanık masaüstü kopyası; yoksa yarı saydam zemin
        self.line = QColor(255, 255, 255, 26)
        self.radius = 14

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outline = QPainterPath()
        outline.addRoundedRect(
            QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), self.radius, self.radius
        )
        if self.backdrop is not None:
            brush = QBrush(self.backdrop)
            ratio = self.backdrop.devicePixelRatio()
            if ratio != 1.0:  # doku fırçası fiziksel pikselle çalışır; mantıksal boyuta ölçekle
                brush.setTransform(QTransform.fromScale(1 / ratio, 1 / ratio))
            painter.fillPath(outline, brush)
        if self.fill is not None:
            painter.fillPath(outline, self.fill)
        painter.setPen(QPen(self.line, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(outline)


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

        self._surface = _Surface(self)
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
        self._apply_surface_colors()
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
        if self._column.count() > 1:  # son eleman esneme boşluğu
            self._column.insertWidget(self._column.count() - 1, make_frame("divider"))
        self._column.insertWidget(self._column.count() - 1, host)

    def set_pinned(self, pinned: bool) -> None:
        self.header.set_pinned(pinned)

    def set_look(self, look: Look) -> None:
        self._look = look
        self.setStyleSheet(look.stylesheet)
        self._apply_surface_colors()

    def card_rect(self) -> QRect:
        """Görünen kartın tamamen açık haldeki ekran konumu."""
        return QRect(self._right - self._width, self._top, self._width, self._height)

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
            # Görüntü paneli göstermeden önce alınır; yoksa panelin kendisi de görüntüye girerdi.
            self._surface.backdrop = (
                backdrop.capture_blurred(screen, self.card_rect()) if self._look.blur else None
            )
            self._surface.update()
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
            self._hide()

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
            self._hide()

    def _hide(self) -> None:
        self.hide()
        self._surface.backdrop = None  # bir sonraki açılışta yeniden alınır
        self.hidden.emit()

    def _apply_surface_colors(self) -> None:
        theme = self._look.theme
        r, g, b = parse_hex(theme.ink)
        self._surface.line = QColor(r, g, b, round(theme.border_alpha * 255))
        self._surface.radius = theme.radius_panel
        r, g, b = parse_hex(theme.bg)
        self._surface.fill = QColor(r, g, b, round(theme.glass_opacity * 255))
        self._surface.update()

    def screen_of_panel(self) -> QScreen:
        return self._screen or QGuiApplication.primaryScreen()
