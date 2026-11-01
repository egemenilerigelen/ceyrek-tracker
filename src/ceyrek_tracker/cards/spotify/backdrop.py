"""Spotify kartının arka planı: kapağın renginden taşan yumuşak ışık, cam yansıması ve nokta dokusu.

Kartın kendi açık yüzeyi yoktur: panelin zemini ve tanesi doğrudan görünür, kart üstünde yüzmez.
Işık, kapağın bulunduğu sol üst köşeden yayılır (kapaktan "yansıyan" ton); ikinci ton sağ altta
sönük bir leke olarak durur; üstten geçen çok hafif bir cam yansıması düz yüzeyi bozar. Hepsinin
üstüne dalgalı bir yarım ton (halftone) nokta deseni biner: noktalar kapağın yanında küçük, uzak
köşede iridir. Desen panelin tanesiyle aynı yönde (metnin tersine) boyandığı için metin
kontrastını azaltmaz, artırır.
Her katman düşük saydamlıktadır (`MAX_ALPHA`, `DOT_ALPHA`). Renkler `palette.py`'den gelir.
Çizim bir kez önbelleğe alınır; hareket yoktur, işlemciye yük bindirmez.
"""

from __future__ import annotations

import math
from functools import lru_cache

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import QFrame, QWidget

from ceyrek_tracker.cards.spotify.palette import DEFAULT, Palette
from ceyrek_tracker.theme import Look

MAX_ALPHA = 0.09  # renk katmanlarının üst sınırı (testle korunur)
DOT_ALPHA = 0.16  # nokta deseninin saydamlığı
DOT_ALPHA_LIGHT = 0.45  # açık temada beyaz nokta krem zeminde çok daha az seçilir
DOT_SPACING = 5.0  # noktalar arası mesafe (px)
DOT_RADIUS = (0.3, 1.7)  # noktanın uzun yarıçapı: kapak köşesinde, uzak köşede (px)
DOT_ASPECT = 0.6  # kısa yarıçap / uzun yarıçap
WAVE_HEIGHT = 0.13  # desenin dalga yüksekliği (kart yüksekliğine oran)
# Açık temada aynı tonlar krem zeminde zaten belirgin; biraz kısılır.
LIGHT_STRENGTH = 0.8


def _color(hex_color: str, alpha: float, cap: float = MAX_ALPHA) -> QColor:
    color = QColor(hex_color)
    color.setAlphaF(min(alpha, cap))
    return color


def _blob(p: QPainter, cx: float, cy: float, rx: float, ry: float, color: QColor) -> None:
    """Kenarı sönen yumuşak elips (ışıma, leke)."""
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


def _shade(dark: bool) -> str:
    """Panelin tanesiyle aynı yön: metnin tersi."""
    return "#000000" if dark else "#ffffff"


@lru_cache(maxsize=4)
def _halftone(width: int, height: int, ratio: float, dark: bool) -> QImage:
    """Dalgalı nokta deseni. Rengi kapaktan bağımsızdır, şarkı değişince yeniden üretilmez."""
    image = QImage(
        round(width * ratio), round(height * ratio), QImage.Format.Format_ARGB32_Premultiplied
    )
    image.setDevicePixelRatio(ratio)
    image.fill(Qt.GlobalColor.transparent)
    w, h = float(width), float(height)
    wave = h * WAVE_HEIGHT
    bend = math.tau * 0.9 / w  # sıraların eğimini veren dalga sayısı

    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    alpha = DOT_ALPHA if dark else DOT_ALPHA_LIGHT
    p.setBrush(_color(_shade(dark), alpha, alpha))
    # Dalga noktaları kaydırdığı için ızgara kartın biraz dışından başlar.
    margin = math.ceil(wave / DOT_SPACING) + 1
    for row in range(-margin, math.ceil(h / DOT_SPACING) + margin):
        for column in range(-1, math.ceil(w / DOT_SPACING) + 2):
            x = (column + (0.5 if row % 2 else 0.0)) * DOT_SPACING
            y = row * DOT_SPACING
            phase = bend * x + math.tau * 0.45 * y / h
            y += wave * math.sin(phase)
            # Kapağın yanında küçük, uzak köşede iri; dalga sınırı düz çizgi olmaktan çıkarır.
            grow = 0.5 * (x / w + y / h) + 0.14 * math.sin(phase + 1.0)
            grow = max(0.0, min(1.0, grow))
            radius = DOT_RADIUS[0] + (DOT_RADIUS[1] - DOT_RADIUS[0]) * grow
            p.save()
            p.translate(x, y)
            p.rotate(math.degrees(math.atan(wave * bend * math.cos(phase))))
            p.drawEllipse(QPointF(0, 0), radius * DOT_ASPECT, radius)
            p.restore()
    p.end()
    return image


def render_backdrop(
    width: int,
    height: int,
    palette: Palette = DEFAULT,
    dark: bool = True,
    ratio: float = 1.0,
    radius: float = 7.0,
) -> QPixmap:
    pixmap = QPixmap(round(width * ratio), round(height * ratio))
    pixmap.setDevicePixelRatio(ratio)
    pixmap.fill(Qt.GlobalColor.transparent)
    if width < 8 or height < 8:
        return pixmap
    w, h = float(width), float(height)
    strength = 1.0 if dark else LIGHT_STRENGTH
    primary, secondary = palette.primary, palette.secondary

    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Kenar çizgisinin içinde kal.
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(1, 1, w - 2, h - 2), radius, radius)
    p.setClipPath(clip)

    # 1) Zemin: sol üstten sağ alta sönen ana ton.
    wash = QLinearGradient(QPointF(0, 0), QPointF(w * 0.85, h))
    wash.setColorAt(0.0, _color(primary, 0.05 * strength))
    wash.setColorAt(1.0, _color(primary, 0.0))
    p.fillRect(QRectF(0, 0, w, h), wash)

    # 2) Kapaktan taşan ışık: kapağın olduğu sol üstten geniş, yumuşak bir ışıma.
    cx, cy = w * 0.17, h * 0.30
    _blob(p, cx, cy, w * 0.62, h * 1.0, _color(primary, MAX_ALPHA * strength))

    # 3) İkinci ton: sağ altta sönük bir leke.
    _blob(p, w * 0.86, h * 0.95, w * 0.38, h * 0.40, _color(secondary, 0.05 * strength))

    # 4) Cam yansıması: köşegen, çok yumuşak bir açık bant.
    sheen = QLinearGradient(QPointF(w * 0.1, 0), QPointF(w * 0.9, h))
    glint = QColor("#ffffff")
    glint.setAlphaF(0.02 if dark else 0.06)
    clear = QColor(glint)
    clear.setAlpha(0)
    sheen.setColorAt(0.30, clear)
    sheen.setColorAt(0.48, glint)
    sheen.setColorAt(0.66, clear)
    p.fillRect(QRectF(0, 0, w, h), sheen)

    # 5) Nokta deseni: ışığın üstüne biner, kartı panelin koyu yüzeyine bağlar.
    p.drawImage(QPointF(0, 0), _halftone(width, height, ratio, dark))
    p.end()
    return pixmap


class SpotifyBackdrop(QFrame):
    """`inner` rolündeki kart çerçevesi; stil sayfası yalnızca kenarlığı çizer (`sunk`: açık yüzey
    yok), kapağın renginden taşan ışık üstüne işlenir, çocuk widget'lar bunun da üstünde kalır."""

    def __init__(self, look: Look, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "inner")
        self.setProperty("sunk", True)
        self._cache: QPixmap | None = None
        self._palette = DEFAULT
        self.set_look(look)

    def set_look(self, look: Look) -> None:
        self._dark = look.theme.name == "dark"
        self._radius = max(1, look.theme.radius_card - 1)
        self._cache = None
        self.update()

    def set_palette(self, palette: Palette) -> None:
        """Şarkı değişince kapağın renkleri."""
        if palette != self._palette:
            self._palette = palette
            self._cache = None
            self.update()

    def resizeEvent(self, event) -> None:
        self._cache = None
        super().resizeEvent(event)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._cache is None:
            self._cache = render_backdrop(
                self.width(),
                self.height(),
                self._palette,
                self._dark,
                self.devicePixelRatioF(),
                self._radius,
            )
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._cache)
