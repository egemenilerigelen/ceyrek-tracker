"""Hava durumu simgeleri: font yerine çizilir, bu yüzden tema vurgusuyla uyumlu kalır.

Renk kuralı: bulut her zaman nötr (gri); vurgu rengi yalnızca etkin hava olayında
(güneş, yağmur, kar, yıldırım, sis çizgileri) kullanılır.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPainterPathStroker, QPen
from PySide6.QtWidgets import QWidget

from ceyrek_tracker.cards.weather import api


def _pen(color: QColor, width: float) -> QPen:
    # Not: QPen(..., cap=...) anahtar sözcüğü PySide6'da çökmeye yol açıyor; ayrı ayrı ayarlanır.
    pen = QPen(color, width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    return pen


class WeatherIcon(QWidget):
    def __init__(self, size: int = 28, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._kind = api.KIND_CLOUDY
        self._color = QColor("#cdc072")
        self._soft = QColor("#bdb5a4")

    def set_kind(self, kind: str) -> None:
        self._kind = kind
        self.update()

    def set_colors(self, accent: str, soft: str) -> None:
        self._color = QColor(accent)
        self._soft = QColor(soft)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self.width()
        width = max(1.4, s / 16)
        p.setPen(_pen(self._color, width))
        p.setBrush(Qt.BrushStyle.NoBrush)
        kind = self._kind
        if kind == api.KIND_CLEAR:
            self._sun(p, QPointF(s / 2, s / 2), s * 0.2, s * 0.34, s * 0.46)
        elif kind == api.KIND_PARTLY:
            cloud = QRectF(s * 0.22, s * 0.4, s * 0.74, s * 0.48)
            # Güneş bulutun arkasında kalır: bulutun çevresinde küçük bir boşluk bırakılır.
            outline = self._cloud_path(cloud)
            stroker = QPainterPathStroker()
            stroker.setWidth(width * 3)
            hidden = outline.united(stroker.createStroke(outline))
            visible = QPainterPath()
            visible.addRect(QRectF(0, 0, s, s))
            p.save()
            p.setClipPath(visible.subtracted(hidden))
            self._sun(
                p, QPointF(s * 0.35, s * 0.35), s * 0.15, s * 0.25, s * 0.34, rays=(3, 4, 5, 6, 7)
            )
            p.restore()
            self._cloud(p, cloud)
        else:
            self._cloud(p, QRectF(s * 0.1, s * 0.2, s * 0.8, s * 0.5))
            if kind == api.KIND_RAIN:
                self._drops(p, s, slanted=True)
            elif kind == api.KIND_SNOW:
                self._drops(p, s, slanted=False, dots=True)
            elif kind == api.KIND_STORM:
                self._bolt(p, s)
            elif kind == api.KIND_FOG:
                for y in (0.78, 0.9):
                    p.drawLine(QPointF(s * 0.2, s * y), QPointF(s * 0.8, s * y))

    def _sun(
        self,
        p: QPainter,
        c: QPointF,
        r: float,
        ray_from: float,
        ray_to: float,
        rays: Iterable[int] = range(8),
    ) -> None:
        """`rays`: 0 doğu, saat yönünde 45° adımlarla (2 güney, 4 batı, 6 kuzey)."""
        p.drawEllipse(c, r, r)
        for i in rays:
            a = i * math.pi / 4
            p.drawLine(
                QPointF(c.x() + math.cos(a) * ray_from, c.y() + math.sin(a) * ray_from),
                QPointF(c.x() + math.cos(a) * ray_to, c.y() + math.sin(a) * ray_to),
            )

    def _cloud_path(self, r: QRectF) -> QPainterPath:
        """Düz tabanlı iki tümsekli bulut: yuvarlatılmış taban ve iki daire birleştirilir."""
        x, y, w, h = r.x(), r.y(), r.width(), r.height()
        base = QPainterPath()
        base.addRoundedRect(QRectF(x, y + h * 0.46, w, h * 0.54), h * 0.27, h * 0.27)
        big = QPainterPath()
        big.addEllipse(QPointF(x + w * 0.4, y + h * 0.44), h * 0.44, h * 0.44)
        small = QPainterPath()
        small.addEllipse(QPointF(x + w * 0.72, y + h * 0.56), h * 0.32, h * 0.32)
        return base.united(big).united(small).simplified()

    def _cloud(self, p: QPainter, r: QRectF) -> None:
        p.save()
        p.setPen(_pen(self._soft, p.pen().widthF()))
        p.drawPath(self._cloud_path(r))
        p.restore()

    def _drops(self, p: QPainter, s: float, slanted: bool, dots: bool = False) -> None:
        for x in (0.3, 0.5, 0.7):
            if dots:
                p.drawEllipse(QPointF(s * x, s * 0.84), s * 0.02, s * 0.02)
            else:
                p.drawLine(
                    QPointF(s * x, s * 0.76), QPointF(s * (x - 0.05 if slanted else x), s * 0.92)
                )

    def _bolt(self, p: QPainter, s: float) -> None:
        path = QPainterPath(QPointF(s * 0.54, s * 0.7))
        for x, y in ((0.44, 0.84), (0.56, 0.84), (0.46, 0.98)):
            path.lineTo(QPointF(s * x, s * y))
        p.drawPath(path)
