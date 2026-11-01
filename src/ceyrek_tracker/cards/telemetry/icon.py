"""Telemetri simgeleri: satır başındaki ve kart başlığındaki ince çizgi resimler.

Segoe MDL2'de karşılığı olmayan (işlemci, bellek çubuğu...) ya da stile uymayan simgeler
bu dosyada çizilir. Hepsi 24x24'lük bir kutuda tasarlanır, tek renklidir (temanın sönük
yazı rengi), bu yüzden açık/koyu temada ve her yazı ölçeğinde uyumlu kalır.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from ceyrek_tracker.theme import Look

BOX = 24.0
STROKE = 1.7
ROW_SIZE_PX = 14
HEADER_SIZE_PX = 15

CPU, MEMORY, GPU, VRAM, POWER, NETWORK, PULSE = (
    "cpu",
    "memory",
    "gpu",
    "vram",
    "power",
    "network",
    "pulse",
)
KINDS = (CPU, MEMORY, GPU, VRAM, POWER, NETWORK, PULSE)


def _lines(p: QPainter, *segments: tuple[float, float, float, float]) -> None:
    for x1, y1, x2, y2 in segments:
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


def _polyline(*points: tuple[float, float]) -> QPainterPath:
    path = QPainterPath(QPointF(*points[0]))
    for point in points[1:]:
        path.lineTo(QPointF(*point))
    return path


def draw_icon(p: QPainter, kind: str) -> None:
    """24x24'lük kutuya, mevcut kalem ve boş fırçayla çizer."""
    if kind == CPU:  # kare yonga: iç çekirdek ve dört kenarda bacaklar
        p.drawRoundedRect(QRectF(5.5, 5.5, 13, 13), 2.2, 2.2)
        p.drawRoundedRect(QRectF(9.5, 9.5, 5, 5), 1, 1)
        for pos in (9.5, 14.5):
            _lines(p, (pos, 2.5, pos, 5.5), (pos, 18.5, pos, 21.5))
            _lines(p, (2.5, pos, 5.5, pos), (18.5, pos, 21.5, pos))
    elif kind == MEMORY:  # RAM çubuğu: gövde ve alttaki bacaklar
        p.drawRoundedRect(QRectF(2.5, 6.5, 19, 9.5), 1.8, 1.8)
        _lines(p, *((x, 16, x, 19.5) for x in (6.5, 10, 14, 17.5)))
        _lines(p, (6.5, 10.5, 17.5, 10.5))
    elif kind == GPU:  # ekran: çerçeve, ayak ve taban
        p.drawRoundedRect(QRectF(3, 4, 18, 12.5), 2.2, 2.2)
        _lines(p, (12, 16.5, 12, 20.5), (8, 20.5, 16, 20.5))
    elif kind == VRAM:  # video belleği: yan yana üç bellek bankası
        for x, top in ((4.5, 8.0), (9.5, 4.5), (14.5, 6.5)):
            p.drawRoundedRect(QRectF(x, top, 4.2, 20 - top), 1.2, 1.2)
        p.drawLine(QPointF(19.8, 8.5), QPointF(21.2, 19.8))
    elif kind == POWER:  # şimşek
        p.drawPath(_polyline((13.5, 2.8), (5.5, 13.2), (11.5, 13.2), (10.5, 21.2), (18.5, 10.2)))
        p.drawLine(QPointF(18.5, 10.2), QPointF(12.8, 10.2))
    elif kind == NETWORK:  # küre: daire, boylam elipsi ve enlem çizgisi
        p.drawEllipse(QRectF(3, 3, 18, 18))
        p.drawEllipse(QRectF(8, 3, 8, 18))
        _lines(p, (3, 12, 21, 12))
    elif kind == PULSE:  # kart başlığı: nabız çizgisi
        p.drawPath(_polyline((2.5, 12), (7, 12), (10, 4.5), (14, 19.5), (17, 12), (21.5, 12)))


class MetricIcon(QWidget):
    def __init__(
        self, kind: str, look: Look, size: int = ROW_SIZE_PX, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        self.setFixedSize(look.metrics.fs(size), look.metrics.fs(size))
        self.set_look(look)

    def set_look(self, look: Look) -> None:
        self._color = QColor(look.theme.text_dim)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.scale(self.width() / BOX, self.height() / BOX)
        pen = QPen(self._color, STROKE, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        draw_icon(p, self.kind)


def header_icon(look: Look) -> QWidget:
    return MetricIcon(PULSE, look, HEADER_SIZE_PX)
