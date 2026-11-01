"""Pano kartının başlık simgesi: düz, tek bir pano (altlık ve üstünde kıskaç).

Segoe MDL2'deki yapıştır simgesi pano üstünde bir sayfa da çizdiği için kullanılmaz; bu simge
çizilir. Tek renktir (başlıktaki diğer simgelerle aynı sönük renk).
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ceyrek_tracker.theme import Look

BOX = 24.0  # çizim birimi: simge 24x24'lük bir kutuda tasarlanır
STROKE = 1.7
SIZE_PX = 15  # başlıktaki simge boyutu (yazı ölçeğiyle büyür)
BOARD = QRectF(4.6, 4.6, 14.8, 17.0)  # altlığın kenar çizgisi
CLIP = QRectF(7.2, 2.0, 9.6, 5.2)  # üstteki dolu kıskaç; altlığın üst kenarını örter


class ClipboardIcon(QWidget):
    def __init__(self, look: Look, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(look.metrics.fs(SIZE_PX), look.metrics.fs(SIZE_PX))
        self.set_look(look)

    def set_look(self, look: Look) -> None:
        self._color = QColor(look.theme.text_dim)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(self.width() / BOX, self.height() / BOX)
        p.setPen(QPen(self._color, STROKE, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(BOARD, 2.6, 2.6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._color)
        p.drawRoundedRect(CLIP, 1.6, 1.6)
