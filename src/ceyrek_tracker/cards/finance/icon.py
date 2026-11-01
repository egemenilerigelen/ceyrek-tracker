"""Satır başı simgesi: sönük bir yazı ($, €, £...) ya da küçük bir çizgi resim, çerçevesiz.

Döviz simgeleri yazıyla, madenler çizimle gösterilir: külçe (gram altın), sikke (çeyrek,
yarım...), bilezik (ayarlı takı altını), ağırlık (ons) ve mücevher (gümüş). Font simgesi
kullanılmaz; renk temadan gelir, bu yüzden açık/koyu temada ve vurgu renginde uyumlu kalır.
Fiyatın dikkatini çalmaması için hepsi aynı, yarı saydam sönük renktedir.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from ceyrek_tracker.theme import Look

# Çizimle gösterilen simgeler; bunların dışındaki her şey yazı olarak çizilir.
BAR, COIN, RING, WEIGHT, GEM = "bar", "coin", "ring", "weight", "gem"
PICTOGRAMS = (BAR, COIN, RING, WEIGHT, GEM)

BOX = 12.0  # çizim birimi: simgeler 12x12'lik bir kutuda tasarlanır
STROKE = 1.0
ALPHA = 0.7  # simgeler isimden ve fiyattan geri planda kalsın
DRAW_SIZE = 0.85  # simgenin satır yüksekliğine oranı


def _polygon(*points: tuple[float, float]) -> QPolygonF:
    return QPolygonF([QPointF(x, y) for x, y in points])


def draw_pictogram(p: QPainter, kind: str) -> None:
    """12x12'lik kutuya, mevcut kalem ve boş fırçayla çizer."""
    if kind == BAR:  # külçe: ön yüz ve üst yüz
        p.drawPolygon(_polygon((0.8, 10.6), (11.2, 10.6), (9.4, 6.2), (2.6, 6.2)))
        p.drawPolyline(_polygon((2.6, 6.2), (4.2, 2.6), (7.8, 2.6), (9.4, 6.2)))
    elif kind == COIN:  # sikke: dış kenar ve iç halka
        p.drawEllipse(QRectF(1, 1, 10, 10))
        p.drawEllipse(QRectF(3.6, 3.6, 4.8, 4.8))
    elif kind == RING:  # bilezik: iç içe iki elips
        p.drawEllipse(QRectF(0.8, 2.2, 10.4, 7.6))
        p.drawEllipse(QRectF(3.4, 4.2, 5.2, 3.6))
    elif kind == GEM:  # mücevher: köşeli elmas ve yüzey çizgileri
        p.drawPolygon(_polygon((6, 1), (11, 5), (6, 11), (1, 5)))
        p.drawPolyline(_polygon((1, 5), (11, 5)))
        p.drawPolyline(_polygon((4, 5), (6, 1), (8, 5), (6, 11), (4, 5)))
    elif kind == WEIGHT:  # ağırlık (ons): tutamaklı kütle
        p.drawPolygon(_polygon((1.6, 10.8), (10.4, 10.8), (8.8, 4.6), (3.2, 4.6)))
        p.drawEllipse(QRectF(4.6, 0.8, 2.8, 2.8))


class SymbolBadge(QWidget):
    def __init__(self, symbol: str, look: Look, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._symbol = symbol
        self._pixel = look.metrics.fs(11)
        self._scale = look.metrics.sp(12) * DRAW_SIZE / BOX
        # Sabit boyut: simgeler isim sütununu kaydırmasın; yükseklik verilmezse düzen
        # simgeyi 0 piksele sıkıştırır.
        sp = look.metrics.sp
        self.setFixedSize(sp(18), sp(14))
        self.set_look(look)

    def set_look(self, look: Look) -> None:
        self._color = QColor(look.theme.text_dim)
        self._color.setAlphaF(ALPHA)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        if self._symbol in PICTOGRAMS:
            p.translate(
                (self.width() - BOX * self._scale) / 2, (self.height() - BOX * self._scale) / 2
            )
            p.scale(self._scale, self._scale)
            pen = QPen(self._color, STROKE)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            draw_pictogram(p, self._symbol)
            return
        font = QFont("Segoe UI")
        font.setPixelSize(self._pixel)
        font.setWeight(QFont.Weight.Normal)
        p.setFont(font)
        p.setPen(self._color)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._symbol)
