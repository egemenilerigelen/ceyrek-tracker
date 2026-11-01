"""Panelin üst bilgisi: solda küçük saat, yanında tarih, gün adı ve açık kalma süresi."""

from __future__ import annotations

import ctypes
import sys
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QToolButton, QVBoxLayout, QWidget

from ceyrek_tracker.core.turkish import format_date
from ceyrek_tracker.core.widgets import make_label, repolish
from ceyrek_tracker.theme import Look

PIN_GLYPH = ""


def uptime_seconds() -> int | None:
    """Windows açılışından beri geçen süre; okunamazsa None."""
    if sys.platform != "win32":
        return None
    func = ctypes.windll.kernel32.GetTickCount64
    func.restype = ctypes.c_ulonglong
    return int(func() // 1000)


def format_uptime(seconds: int) -> str:
    minutes = seconds // 60
    days, rest = divmod(minutes, 24 * 60)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days}g {hours}s"
    if hours:
        return f"{hours}s {mins}dk"
    return f"{mins}dk"


def format_clock(now: datetime) -> str:
    """'01:21'"""
    return f"{now:%H:%M}"


def format_uptime_line(uptime: int) -> str:
    """'Açık 12s 48dk'"""
    return f"Açık {format_uptime(uptime)}"


class HeaderBar(QWidget):
    """Kompakt düzen: solda saat, yanında iki satırlık küçük tarih ve açık kalma süresi."""

    pin_clicked = Signal()

    def __init__(self, look: Look, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(look.metrics.sp(8))
        self._clock = make_label("", "clock")
        row.addWidget(self._clock)

        details = QVBoxLayout()
        details.setContentsMargins(0, 0, 0, 0)
        details.setSpacing(0)
        self._date = make_label("", "header_date")
        self._uptime = make_label("", "header")
        details.addStretch(1)
        details.addWidget(self._date)
        details.addWidget(self._uptime)
        details.addStretch(1)
        row.addLayout(details, 1)

        self._pin = QToolButton()
        self._pin.setProperty("role", "icon")
        self._pin.setText(PIN_GLYPH)
        self._pin.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pin.clicked.connect(self.pin_clicked)
        row.addWidget(self._pin)
        self.set_pinned(False)

        # Dakika başında bir kez çalışır; yalnızca panel açıkken aktif.
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._tick)

    def set_pinned(self, pinned: bool) -> None:
        self._pin.setProperty("active", pinned)
        self._pin.setToolTip("Sabitlemeyi kaldır" if pinned else "Paneli açık tut")
        repolish(self._pin)

    def start(self) -> None:
        self._tick()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        now = datetime.now()
        uptime = uptime_seconds()
        self._clock.setText(format_clock(now))
        self._date.setText(format_date(now.date()))
        self._uptime.setText("" if uptime is None else format_uptime_line(uptime))
        self._uptime.setVisible(uptime is not None)
        self._timer.start((60 - now.second) * 1000 - now.microsecond // 1000 + 100)
