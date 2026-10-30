"""Hava durumu kartının arka planı: havaya göre renk lekesi, küçük bir desen ve ince tane.

Arka plan yalnızca atmosfer verir; metnin okunabilirliğini bozmamak için her katman
`MAX_ALPHA` ile sınırlıdır ve renk/desen kartın sağında (simgenin olduğu yerde) yoğunlaşıp
sola doğru sönerek metin tarafını sakin bırakır. Çizim bir kez önbelleğe alınır.
"""

from __future__ import annotations

import random

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QFrame, QWidget

from ceyrek_tracker.cards.weather import api
from ceyrek_tracker.theme import Look

MAX_ALPHA = 0.15  # renk katmanlarının üst sınırı (testle korunur)
GRAIN_ALPHA = 0.05  # tane/desen çizgilerinin üst sınırı

# Havaya göre (ana ton, ikinci ton).
TINTS: dict[str, tuple[str, str]] = {
    api.KIND_CLEAR: ("#e8a935", "#d9742f"),
    api.KIND_PARTLY: ("#e8b955", "#7f98b5"),
    api.KIND_CLOUDY: ("#8a9bb0", "#5f6f85"),
    api.KIND_FOG: ("#98a4b0", "#7a8694"),
    api.KIND_RAIN: ("#4f86c6", "#3a5f94"),
    api.KIND_SNOW: ("#7fb0d8", "#5f93c0"),
    api.KIND_STORM: ("#7b6ad8", "#f0c040"),
}


def _color(hex_color: str, alpha: float, cap: float = MAX_ALPHA) -> QColor:
    color = QColor(hex_color)
    color.setAlphaF(min(alpha, cap))
    return color


def _blob(p: QPainter, cx: float, cy: float, rx: float, ry: float, color: QColor) -> None:
    """Kenarı sönen yumuşak elips (bulut, sis, güneş hâlesi)."""
    p.save()
    p.translate(cx, cy)
    p.scale(1.0, ry / rx)
    gradient = QRadialGradient(QPointF(0, 0), rx)
    gradient.setColorAt(0.0, color)
    faded = QColor(color)
    faded.setAlpha(0)
    gradient.setColorAt(1.0, faded)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(gradient)
    p.drawEllipse(QPointF(0, 0), rx, rx)
    p.restore()


def _streaks(p: QPainter, rng: random.Random, w: float, h: float, tint: str, count: int) -> None:
    pen = QPen(_color(tint, 0.2), 1.0)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    for _ in range(count):
        x = rng.uniform(w * 0.25, w * 1.05)  # sol taraf (metin) daha seyrek
        y = rng.uniform(-8, h)
        length = rng.uniform(7, 14)
        p.drawLine(QPointF(x, y), QPointF(x - length * 0.35, y + length))


def render_backdrop(kind: str, width: int, height: int, ink: str, ratio: float = 1.0) -> QPixmap:
    pixmap = QPixmap(round(width * ratio), round(height * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    if width < 8 or height < 8:
        return pixmap

    primary, secondary = TINTS.get(kind, TINTS[api.KIND_CLOUDY])
    rng = random.Random(f"{kind}:{width}x{height}")  # her çizimde aynı desen, titreme yok
    w, h = float(width), float(height)

    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Kenar çizgisinin içinde kal.
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(1, 1, w - 2, h - 2), 7, 7)
    p.setClipPath(clip)

    # 1) Zemin: sağ üstten sol alta sönen ikinci ton.
    wash = QLinearGradient(QPointF(w, 0), QPointF(w * 0.15, h))
    wash.setColorAt(0.0, _color(secondary, 0.09))
    wash.setColorAt(1.0, _color(secondary, 0.0))
    p.fillRect(QRectF(0, 0, w, h), wash)

    # 2) Ana ton: simgenin olduğu sağ üst köşede ışıma.
    sx, sy = w * 0.88, h * 0.2
    _blob(p, sx, sy, w * 0.42, h * 0.75, _color(primary, MAX_ALPHA))

    # 3) Havaya özgü desen.
    if kind == api.KIND_CLEAR:
        for radius, alpha in ((h * 0.36, 0.10), (h * 0.62, 0.06), (h * 0.9, 0.035)):
            p.setPen(QPen(_color(primary, alpha, GRAIN_ALPHA * 2), 1.0))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(sx, sy), radius, radius)
    elif kind in (api.KIND_PARTLY, api.KIND_CLOUDY):
        cloud = _color(secondary, 0.14)
        _blob(p, w * 0.62, h * 0.30, w * 0.26, h * 0.20, cloud)
        _blob(p, w * 0.90, h * 0.62, w * 0.30, h * 0.24, cloud)
        _blob(p, w * 0.45, h * 0.86, w * 0.24, h * 0.16, _color(secondary, 0.09))
    elif kind == api.KIND_FOG:
        for fy, alpha in ((0.25, 0.12), (0.55, 0.10), (0.85, 0.12)):
            _blob(p, w * 0.78, h * fy, w * 0.62, h * 0.12, _color(primary, alpha))
    elif kind == api.KIND_RAIN:
        _streaks(p, rng, w, h, primary, round(w * h / 420))
    elif kind == api.KIND_SNOW:
        p.setPen(Qt.PenStyle.NoPen)
        for _ in range(round(w * h / 520)):
            x = rng.uniform(w * 0.3, w)
            y = rng.uniform(0, h)
            p.setBrush(_color(secondary, rng.uniform(0.14, 0.22)))
            p.drawEllipse(QPointF(x, y), rng.uniform(0.8, 1.7), rng.uniform(0.8, 1.7))
    elif kind == api.KIND_STORM:
        _streaks(p, rng, w, h, primary, round(w * h / 600))
        _blob(p, w * 0.78, h * 0.92, w * 0.30, h * 0.30, _color(secondary, 0.14))

    # 4) İnce tane: düz yüzeye hafif doku verir.
    p.setPen(Qt.PenStyle.NoPen)
    for _ in range(round(w * h / 38)):
        p.setBrush(_color(ink, rng.uniform(0.012, 0.04), GRAIN_ALPHA))
        p.drawRect(QRectF(rng.uniform(0, w), rng.uniform(0, h), 1.0, 1.0))
    p.end()
    return pixmap


class WeatherBackdrop(QFrame):
    """`inner` rolündeki kart çerçevesi; stil sayfası zemini ve kenarlığı çizdikten sonra
    havaya göre arka planı üstüne işler, çocuk widget'lar bunun da üstünde kalır."""

    def __init__(self, look: Look, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "inner")
        self._ink = look.theme.ink
        self._kind = api.KIND_CLOUDY
        self._cache: QPixmap | None = None

    def set_kind(self, kind: str) -> None:
        if kind != self._kind:
            self._kind = kind
            self._cache = None
            self.update()

    def set_look(self, look: Look) -> None:
        self._ink = look.theme.ink
        self._cache = None
        self.update()

    def resizeEvent(self, event) -> None:
        self._cache = None
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._cache is None:
            self._cache = render_backdrop(
                self._kind, self.width(), self.height(), self._ink, self.devicePixelRatioF()
            )
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._cache)
