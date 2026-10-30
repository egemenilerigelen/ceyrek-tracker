"""Panelin zemini: yarı saydam, yuvarlak köşeli, hafif dokulu cam benzeri yüzey.

Windows 10'un yerleşik bulanık cam efekti pencere bölgesini yok sayıp tüm dikdörtgeni boyadığı
için köşeler kesilemiyor. Bu yüzden zemin tamamen Qt ile çizilir (köşeler antialiased) ve cam
hissi tasarımla verilir:

- aşağı doğru derinleşen zemin (üst kenar ışık alıyormuş gibi daha açık kalır),
- ince tane dokusu: düz yüzeyi plastik gösterme ve arkadaki pencerelerin silik hayaletini dağıtma,
- üstü daha parlak, altı sönük gradyan kenarlık.

Derinleşme ve tane, metin renginin *tersi* yönde (koyu temada siyaha, açık temada beyaza) boyanır;
böylece metin kontrastını azaltmaz, artırır. Okunabilirlik testlerle korunur.
Çizim bir kez önbelleğe alınır; çocuk widget'lar (saat, kartlar) yenilenince yeniden üretilmez.
"""

from __future__ import annotations

import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QWidget

from ceyrek_tracker.theme import Look
from ceyrek_tracker.theme.tokens import Theme, blend

DEPTH = 0.14  # zeminin alt kenarındaki derinleşme oranı
GRAIN_MAX_ALPHA = 0.06  # tane noktalarının en yüksek alfası
GRAIN_TILE = 160  # tane dokusunun tekrar eden karesi (px)
BORDER_TOP_ALPHA = 0.20
BORDER_BOTTOM_ALPHA = 0.06


def _alpha(color: str, alpha: float) -> QColor:
    result = QColor(color)
    result.setAlphaF(max(0.0, min(1.0, alpha)))
    return result


def _grain_tile(shade: str) -> QPixmap:
    """Yatay ve dikeyde sürekli tekrar eden, deterministik ince tane karesi."""
    rng = random.Random(7)  # her çizimde aynı doku, titreme yok
    tile = QPixmap(GRAIN_TILE, GRAIN_TILE)
    tile.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tile)
    painter.setPen(Qt.PenStyle.NoPen)
    for _ in range(GRAIN_TILE * GRAIN_TILE // 22):
        painter.setBrush(_alpha(shade, rng.uniform(0.2, 1.0) * GRAIN_MAX_ALPHA))
        painter.drawRect(QRectF(rng.randrange(GRAIN_TILE), rng.randrange(GRAIN_TILE), 1, 1))
    painter.end()
    return tile


def render_surface(theme: Theme, width: int, height: int, ratio: float = 1.0) -> QPixmap:
    """Panel zeminini (mantıksal `width` x `height`) saydam bir pixmap'e çizer."""
    pixmap = QPixmap(round(width * ratio), round(height * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    if width < 4 or height < 4:
        return pixmap

    w, h = float(width), float(height)
    outline = QPainterPath()
    outline.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), theme.radius_panel, theme.radius_panel)
    opacity = theme.glass_opacity

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Metin renginin tersi: koyu temada siyah, açık temada beyaz.
    shade = "#000000" if theme.ink.lower() == "#ffffff" else "#ffffff"

    # 1) Zemin: ayarlardaki saydamlıkla boyanır, aşağı doğru derinleşir.
    base = QLinearGradient(QPointF(0, 0), QPointF(0, h))
    base.setColorAt(0.0, _alpha(theme.bg, opacity))
    base.setColorAt(0.35, _alpha(theme.bg, opacity))
    base.setColorAt(1.0, _alpha(blend(shade, theme.bg, DEPTH), opacity))
    painter.fillPath(outline, base)

    # 2) İnce tane.
    painter.fillPath(outline, QBrush(_grain_tile(shade)))

    # 3) Kenarlık: üstte parlak, altta sönük.
    border = QLinearGradient(QPointF(0, 0), QPointF(0, h))
    border.setColorAt(0.0, _alpha(theme.ink, BORDER_TOP_ALPHA))
    border.setColorAt(0.3, _alpha(theme.ink, theme.border_alpha))
    border.setColorAt(1.0, _alpha(theme.ink, BORDER_BOTTOM_ALPHA))
    painter.setPen(QPen(QBrush(border), 1))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(outline)
    painter.end()
    return pixmap


class PanelSurface(QWidget):
    """Panelin çizilen yüzeyi; içine üst bilgi ve kartlar yerleştirilir."""

    def __init__(self, look: Look, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = look.theme
        self._cache: QPixmap | None = None

    def set_look(self, look: Look) -> None:
        self._theme = look.theme
        self._cache = None
        self.update()

    def resizeEvent(self, event) -> None:
        self._cache = None
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        if self._cache is None:
            self._cache = render_surface(
                self._theme, self.width(), self.height(), self.devicePixelRatioF()
            )
        QPainter(self).drawPixmap(0, 0, self._cache)
