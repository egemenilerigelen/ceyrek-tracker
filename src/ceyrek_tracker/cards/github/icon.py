"""GitHub kartının başlık simgesi: katkı tablosunu andıran 3x3'lük küçük kareler.

Segoe MDL2'de GitHub logosu yoktur; simge çizilir. Tek renklidir (başlıktaki diğer simgelerle
aynı sönük renk), karelerin soluklukları katkı basamaklarını taklit eder.
"""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from ceyrek_tracker.theme import Look

BOX = 24.0  # çizim birimi: simge 24x24'lük bir kutuda tasarlanır
SIZE_PX = 15  # başlıktaki simge boyutu (yazı ölçeğiyle büyür)
CELL = 5.4
GAP = 2.4
ORIGIN = (BOX - (3 * CELL + 2 * GAP)) / 2
ALPHAS = ((0.35, 0.65, 1.0), (0.65, 1.0, 0.35), (1.0, 0.35, 0.65))  # satır satır


class GithubIcon(QWidget):
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
        p.setPen(Qt.PenStyle.NoPen)
        for row, alphas in enumerate(ALPHAS):
            for column, alpha in enumerate(alphas):
                color = QColor(self._color)
                color.setAlphaF(color.alphaF() * alpha)
                p.setBrush(color)
                x = ORIGIN + column * (CELL + GAP)
                y = ORIGIN + row * (CELL + GAP)
                p.drawRoundedRect(QRectF(x, y, CELL, CELL), 1.2, 1.2)
