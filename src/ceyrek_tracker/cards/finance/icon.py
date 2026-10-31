"""Satır başı simgesi: yalnızca sönük bir yazı ($, €, Au...), çerçevesiz.

Font simgesi yerine çizilir; rengi temadan gelir, bu yüzden açık/koyu temada ve vurgu
renginde uyumlu kalır. Fiyatın dikkatini çalmaması için hepsi aynı sönük renktedir.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import QWidget

from ceyrek_tracker.theme import Look


class SymbolBadge(QWidget):
    def __init__(self, symbol: str, look: Look, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._symbol = symbol
        self._pixel = look.metrics.fs(11)
        # Sabit boyut: tek ve çift harfli simgeler isim sütununu kaydırmasın; yükseklik
        # verilmezse düzen simgeyi 0 piksele sıkıştırır.
        sp = look.metrics.sp
        self.setFixedSize(sp(18), sp(14))
        self.set_look(look)

    def set_look(self, look: Look) -> None:
        self._color = QColor(look.theme.text_dim)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        font = QFont("Segoe UI")
        font.setPixelSize(self._pixel)
        font.setWeight(QFont.Weight.DemiBold)
        p.setFont(font)
        p.setPen(self._color)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._symbol)
