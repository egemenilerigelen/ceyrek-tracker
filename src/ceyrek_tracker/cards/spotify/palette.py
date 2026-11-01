"""Kapak resminden renkler: arka plan ışıması ve vurgu rengi şarkının tonunu yansıtsın.

Tüm kararlar algısal OKLCH uzayında verilir (L: algılanan parlaklık, C: canlılık, h: ton). HSL
burada güvenilmezdir: neredeyse siyah ya da neredeyse beyaz bir piksel HSL'de "tam doygun"
görünür, aynı HSL parlaklığındaki sarı da laciverte göre iki kat parlak algılanır.

Seçim adımları:
1. Spotify görselinin yanları ve logolu bandı kırpılır, resim küçültülür.
2. Canlılığı düşük pikseller (siyah, beyaz, gri, sepya gürültüsü) ton oylamasına katılmaz.
3. Kalan pikseller ton çemberinde oy kullanır; oy canlılığın karesiyle orantılıdır, böylece az
   ama canlı bir renk, çok ama soluk bir tonun önüne geçebilir. Oylar komşu tonlara yayılır:
   tek bir renk, iki dilimin sınırına düştüğü için bölünmez.
4. Çıkan ton sabit bir algısal parlaklığa oturtulur: her kapakta ışıma eşit güçte görünür.
   Canlılık kapağınkini aşmaz: soluk kapağa uydurma renk verilmez, gri kapak gri kalır.

Kapak yoksa varsayılan zeytin-yeşil kullanılır.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage

from ceyrek_tracker.cards.spotify.widgets import art_rect
from ceyrek_tracker.theme import Theme
from ceyrek_tracker.theme.tokens import blend, contrast_ratio, parse_hex

SAMPLE = 32  # resim bu boyuta küçültülür
MIN_CHROMA = 0.03  # bundan soluk piksel renksiz sayılır, oy kullanmaz
MIN_LIGHTNESS = 0.12  # bundan koyu piksel siyah sayılır (kapak sıkıştırma gürültüsü)
VOTE_CHROMA_CAP = 0.16  # oyda canlılık üst sınırı: aşırı doygun küçük leke her şeyi ezmesin
MIN_AREA = 0.03  # bir ton, görünen alanın en az bu kadarını kaplamalı

HUE_BINS = 72  # 5 derecelik dilimler
HUE_BIN_DEGREES = 360 / HUE_BINS
SPREAD_BINS = 4  # oy iki yana 20 dereceye kadar yayılır
TONE_WINDOW = 25.0  # bir tonun ortalamasına giren pikseller (derece)
SECOND_TONE_GAP = 50.0  # ikinci ton ana tondan en az bu kadar uzak olmalı
SECOND_TONE_STRENGTH = 0.15  # ikinci tonun oyu, ana tonun oyuna göre en az bu oranda olmalı
NEIGHBOUR_HUE = 28.0  # ikinci renk yoksa ana tonun bu kadar komşusu kullanılır

GLOW_LIGHTNESS = 0.62  # ışıma tonunun algısal parlaklığı: tüm kapaklarda aynı
GLOW_CHROMA = (0.02, 0.14)

ACCENT_LIGHTNESS = {"dark": 0.80, "light": 0.45}  # çubuk ve düğmelerin algısal parlaklığı
ACCENT_LIMITS = (0.20, 0.95)
ACCENT_BOOST = 1.3  # vurgu, kapağın tonundan biraz canlıdır
ACCENT_CHROMA = 0.15
MIN_CONTRAST = 3.0  # çubuk gibi çizgisel öğeler için WCAG alt sınırı
GLOW_PEAK = 0.20  # çubuğun altındaki ışımanın en yoğun hâli (kontrol bunun üstünde yapılır)

# Kapak yokken: referanstaki zeytin-yeşil tonları.
LIME, GREEN = "#b8b330", "#5aa63a"


@dataclass(frozen=True)
class Palette:
    primary: str  # ışıma tonu
    secondary: str
    hue: float | None = None  # kapağın ana tonu (derece); renksiz kapakta None
    chroma: float = 0.0  # kapağın ana tonunun canlılığı


DEFAULT = Palette(LIME, GREEN)

_LINEAR = tuple(
    v / 255 / 12.92 if v / 255 <= 0.04045 else ((v / 255 + 0.055) / 1.055) ** 2.4
    for v in range(256)
)


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def _oklab(red: int, green: int, blue: int) -> tuple[float, float, float]:
    """8 bit sRGB -> OKLab (Björn Ottosson, 2020)."""
    r, g, b = _LINEAR[red], _LINEAR[green], _LINEAR[blue]
    long_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    medium = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    short = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (
        0.2104542553 * long_ + 0.7936177850 * medium - 0.0040720468 * short,
        1.9779984951 * long_ - 2.4285922050 * medium + 0.4505937099 * short,
        0.0259040371 * long_ + 0.7827717662 * medium - 0.8086757660 * short,
    )


def oklch(color: str) -> tuple[float, float, float]:
    """'#rrggbb' -> (L, C, h derece)."""
    lightness, a, b = _oklab(*parse_hex(color))
    return lightness, math.hypot(a, b), math.degrees(math.atan2(b, a)) % 360


def _linear_rgb(lightness: float, a: float, b: float) -> tuple[float, float, float]:
    long_ = (lightness + 0.3963377774 * a + 0.2158037573 * b) ** 3
    medium = (lightness - 0.1055613458 * a - 0.0638541728 * b) ** 3
    short = (lightness - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        4.0767416621 * long_ - 3.3077115913 * medium + 0.2309699292 * short,
        -1.2684380046 * long_ + 2.6097574011 * medium - 0.3413193965 * short,
        -0.0041960863 * long_ - 0.7034186147 * medium + 1.7076147010 * short,
    )


def _encode(value: float) -> int:
    value = _clamp(value, 0.0, 1.0)
    value = value * 12.92 if value <= 0.0031308 else 1.055 * value ** (1 / 2.4) - 0.055
    return round(value * 255)


def to_hex(lightness: float, chroma: float, hue: float) -> str:
    """OKLCH -> '#rrggbb'. Ekranın gösteremediği renkte yalnızca canlılık kısılır."""
    angle = math.radians(hue)

    def rgb_at(c: float) -> tuple[float, float, float]:
        return _linear_rgb(lightness, c * math.cos(angle), c * math.sin(angle))

    def fits(c: float) -> bool:
        return all(-0.0001 <= v <= 1.0001 for v in rgb_at(c))

    low, high = 0.0, chroma
    if not fits(high):
        for _ in range(16):
            middle = (low + high) / 2
            low, high = (middle, high) if fits(middle) else (low, middle)
        high = low
    return "#{:02x}{:02x}{:02x}".format(*(_encode(v) for v in rgb_at(high)))


def _gap(a: float, b: float) -> float:
    """Ton çemberinde iki açı arasındaki uzaklık."""
    gap = abs(a - b) % 360
    return min(gap, 360 - gap)


def _sample(data: bytes) -> tuple[list[tuple[float, float, float, float]], int] | None:
    """Canlı pikseller (a, b, canlılık, oy) ve görünen piksel sayısı; resim okunamazsa None."""
    image = QImage.fromData(data)
    if image.isNull():
        return None
    if (crop := art_rect(image)) is not None:
        image = image.copy(crop)  # Spotify'ın şeffaf yanları ve logolu bandı
    small = image.scaled(
        SAMPLE,
        SAMPLE,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    ).convertToFormat(QImage.Format.Format_ARGB32)
    raw = bytes(small.constBits())  # piksel başına B, G, R, A
    stride = small.bytesPerLine()
    pixels = []
    visible = 0
    for y in range(SAMPLE):
        for x in range(SAMPLE):
            offset = y * stride + x * 4
            if raw[offset + 3] < 128:
                continue
            visible += 1
            lightness, a, b = _oklab(raw[offset + 2], raw[offset + 1], raw[offset])
            chroma = math.hypot(a, b)
            if chroma >= MIN_CHROMA and lightness >= MIN_LIGHTNESS:
                pixels.append((a, b, chroma, min(chroma, VOTE_CHROMA_CAP) ** 2))
    return pixels, visible


def _vote(pixels: list[tuple[float, float, float, float]]) -> list[float]:
    """Ton oylaması; her oy komşu dilimlere üçgen biçiminde yayılır."""
    bins = [0.0] * HUE_BINS
    for a, b, _, vote in pixels:
        bins[int(math.degrees(math.atan2(b, a)) % 360 / HUE_BIN_DEGREES) % HUE_BINS] += vote
    return [
        sum(
            bins[(index + step) % HUE_BINS] * (SPREAD_BINS + 1 - abs(step))
            for step in range(-SPREAD_BINS, SPREAD_BINS + 1)
        )
        for index in range(HUE_BINS)
    ]


def _members(pixels: list, hue: float) -> list:
    return [
        p for p in pixels if _gap(math.degrees(math.atan2(p[1], p[0])) % 360, hue) <= TONE_WINDOW
    ]


def _tone_of(members: list) -> tuple[float, float]:
    """Pikselleri oy ağırlıklı ortalar: (ton, canlılık). Ton dairesel ortalamayla bulunur."""
    total = sum(p[3] for p in members)
    a = sum(p[0] * p[3] for p in members) / total
    b = sum(p[1] * p[3] for p in members) / total
    return math.degrees(math.atan2(b, a)) % 360, sum(p[2] * p[3] for p in members) / total


def _glow(hue: float, chroma: float) -> str:
    return to_hex(GLOW_LIGHTNESS, _clamp(chroma, *GLOW_CHROMA), hue)


def extract_palette(data: bytes | None) -> Palette:
    sampled = _sample(data) if data else None
    if sampled is None or sampled[1] == 0:
        return DEFAULT
    pixels, visible = sampled
    votes = _vote(pixels) if pixels else []
    peak = max(range(HUE_BINS), key=votes.__getitem__) if pixels else 0
    peak_hue = (peak + 0.5) * HUE_BIN_DEGREES
    members = _members(pixels, peak_hue)
    if len(members) / visible < MIN_AREA:
        neutral = to_hex(GLOW_LIGHTNESS, 0.0, 0.0)  # siyah-beyaz kapak
        return Palette(neutral, neutral)

    hue, chroma = _tone_of(members)
    primary = _glow(hue, chroma)
    # İkinci ton: kapakta belirgin, ana tondan uzak başka bir renk; yoksa ana tonun komşusu.
    others = [
        index
        for index in range(HUE_BINS)
        if _gap((index + 0.5) * HUE_BIN_DEGREES, hue) >= SECOND_TONE_GAP
        and votes[index] >= SECOND_TONE_STRENGTH * votes[peak]
    ]
    if others:
        other_peak = max(others, key=votes.__getitem__)
        other = _members(pixels, (other_peak + 0.5) * HUE_BIN_DEGREES)
        if len(other) / visible >= MIN_AREA:
            return Palette(primary, _glow(*_tone_of(other)), hue, chroma)
    return Palette(primary, _glow(hue + NEIGHBOUR_HUE, chroma), hue, chroma)


def groove_behind_bar(theme: Theme, glow: str) -> str:
    """Çubuğun gerçekten üzerinde durduğu renk: panel, en yoğun ışıma, boş çubuk. Kartın kendi
    yüzeyi yoktur (`SpotifyBackdrop`), panel doğrudan görünür."""
    lit = blend(glow, theme.bg, GLOW_PEAK)
    return blend(theme.ink, lit, theme.surface_hover_alpha)


def accent_for(palette: Palette, theme: Theme) -> str | None:
    """Şarkı çubuğu ve düğmeler için vurgu rengi. Parlaklığı temaya göre sabittir; çubuğun gerçek
    zemininde okunmuyorsa zeminden uzaklaştırılır. Kapak yoksa `None`: tema vurgusu kalır."""
    if palette == DEFAULT:
        return None
    hue = palette.hue if palette.hue is not None else 0.0
    chroma = min(palette.chroma * ACCENT_BOOST, ACCENT_CHROMA)
    lightness = ACCENT_LIGHTNESS.get(theme.name, ACCENT_LIGHTNESS["dark"])
    step = 0.01 if theme.name == "dark" else -0.01
    groove = groove_behind_bar(theme, palette.primary)
    color = to_hex(lightness, chroma, hue)
    while contrast_ratio(color, groove) < MIN_CONTRAST and (
        ACCENT_LIMITS[0] < lightness < ACCENT_LIMITS[1]
    ):
        lightness += step
        color = to_hex(lightness, chroma, hue)
    return color
