"""Monokrom Spotify logosu (kart başlığındaki simge).

Başlık simgeleri Segoe MDL2 yazı tipinden gelir; yazı tipinde Spotify logosu olmadığı için bu
logo çizilir: bir daire ve içine oyulmuş üç ses dalgası. Tek renktir (başlıktaki diğer simgelerle
aynı sönük renk); dalgalar boyanmaz, daireden kesilip çıkarılır.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPainterPathStroker
from PySide6.QtWidgets import QWidget

from ceyrek_tracker.theme import Look

BOX = 24.0  # çizim birimi: logo 24x24'lük bir kutuda tasarlanır
# Üç dalga: (sol uç x, uç y, denetim noktası y, sağ uç x, kalınlık). Üstteki en uzun ve kalın.
WAVES = (
    (4.6, 9.6, 5.8, 19.4, 2.3),
    (5.6, 13.2, 10.0, 18.4, 2.0),
    (6.8, 16.5, 14.0, 17.2, 1.7),
)
SIZE_PX = 15  # başlıktaki simge boyutu (yazı ölçeğiyle büyür)


def logo_path() -> QPainterPath:
    """24x24'lük kutuda logo: daire eksi üç dalga."""
    circle = QPainterPath()
    circle.addEllipse(QRectF(0.5, 0.5, BOX - 1, BOX - 1))
    cut = QPainterPath()
    for left, y, control_y, right, width in WAVES:
        wave = QPainterPath(QPointF(left, y))
        wave.quadTo(QPointF((left + right) / 2, control_y), QPointF(right, y))
        stroker = QPainterPathStroker()
        stroker.setWidth(width)
        stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
        cut = cut.united(stroker.createStroke(wave))
    return circle.subtracted(cut)


class SpotifyLogo(QWidget):
    def __init__(self, look: Look, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path = logo_path()
        self.setFixedSize(look.metrics.fs(SIZE_PX), look.metrics.fs(SIZE_PX))
        self.set_look(look)

    def set_look(self, look: Look) -> None:
        self._color = QColor(look.theme.text_dim)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(self.width() / BOX, self.height() / BOX)
        p.fillPath(self._path, self._color)
