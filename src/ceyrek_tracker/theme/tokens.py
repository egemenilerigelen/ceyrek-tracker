"""Tasarım belirteçleri (token): panelin görünümünü belirleyen tüm değerler burada.

Kartlarda ve pencerede sabit renk, boyut ya da yazı tipi yazılmaz; hepsi `Theme`
(renk, şekil, yazı tipi) ve `Metrics` (yoğunluk, yazı ölçeği) üzerinden okunur.
Görünümü değiştirmek için bu dosyadaki ön ayarları ya da settings.json içindeki
`theme`, `accent`, `density`, `font_scale` alanlarını değiştirmek yeterlidir.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

UI_FONT = "'Segoe UI Variable Text', 'Segoe UI', sans-serif"
# Başlık düğmeleri ve kart simgeleri bu simge yazı tipindeki karakterlerle çizilir.
ICON_FONT = "Segoe MDL2 Assets"


def parse_hex(color: str) -> tuple[int, int, int]:
    return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def rgba(color: str, alpha: float) -> str:
    """'#rrggbb' + saydamlık -> Qt stil sayfasının anladığı 'rgba(r, g, b, a)'."""
    r, g, b = parse_hex(color)
    return f"rgba({r}, {g}, {b}, {alpha:.3f})"


def blend(foreground: str, background: str, alpha: float) -> str:
    """`foreground` rengini `alpha` saydamlıkla `background` üstüne karıştırır."""
    mixed = (
        round(alpha * f + (1 - alpha) * b)
        for f, b in zip(parse_hex(foreground), parse_hex(background), strict=True)
    )
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def _luminance(color: str) -> float:
    def channel(value: int) -> float:
        c = value / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in parse_hex(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(color_a: str, color_b: str) -> float:
    """WCAG kontrast oranı; okunabilirlik için metin en az 4,5 olmalı."""
    light, dark = sorted((_luminance(color_a), _luminance(color_b)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


@dataclass(frozen=True)
class Theme:
    name: str
    # Panel zemini `bg` renginin `glass_opacity` kadar opak boyanmış hâlidir.
    bg: str
    glass_opacity: float
    # Yüzeyler ve çizgiler `ink` renginin saydam tonlarıdır (koyu temada beyaz).
    ink: str
    surface_alpha: float
    surface_hover_alpha: float
    border_alpha: float
    # Vurgu
    accent: str
    accent_2: str
    # Metin
    text: str
    text_soft: str
    text_dim: str
    # Anlam renkleri: duvar kağıdına, temaya göre kaymaz.
    up: str
    down: str
    warn: str
    # Şekil
    radius_panel: int = 14
    radius_card: int = 8
    radius_small: int = 6

    @property
    def surface(self) -> str:
        return rgba(self.ink, self.surface_alpha)

    @property
    def surface_hover(self) -> str:
        return rgba(self.ink, self.surface_hover_alpha)

    @property
    def border(self) -> str:
        return rgba(self.ink, self.border_alpha)

    def with_accent(self, accent: str) -> Theme:
        return replace(self, accent=accent)

    def with_glass_opacity(self, opacity: float) -> Theme:
        return replace(self, glass_opacity=opacity)


# Sıcak kömür cam + zeytin-altın vurgu.
DARK = Theme(
    name="dark",
    bg="#15130f",
    glass_opacity=0.92,
    ink="#ffffff",
    surface_alpha=0.06,
    surface_hover_alpha=0.10,
    border_alpha=0.10,
    accent="#cdc072",
    accent_2="#bfaf95",
    text="#f2ede3",
    text_soft="#bdb5a4",
    text_dim="#a39b8b",
    up="#66c78f",
    down="#ef7b6c",
    warn="#f0a040",
)

LIGHT = Theme(
    name="light",
    bg="#f4f1ea",
    glass_opacity=0.92,
    ink="#1d1a14",
    surface_alpha=0.05,
    surface_hover_alpha=0.09,
    border_alpha=0.12,
    accent="#6b6212",
    accent_2="#7d6f55",
    text="#1f1c16",
    text_soft="#4a4438",
    text_dim="#665f50",
    up="#1b7f48",
    down="#b8352a",
    warn="#9a5a00",
)

THEMES: dict[str, Theme] = {DARK.name: DARK, LIGHT.name: LIGHT}


# Yoğunluk ön ayarları: boşluk çarpanı.
DENSITIES: dict[str, float] = {"compact": 0.86, "normal": 1.0, "relaxed": 1.16}


@dataclass(frozen=True)
class Metrics:
    """Boyutlar Normal yoğunlukta ve %100 yazı ölçeğinde verilir; burada ölçeklenir."""

    spacing: float = 1.0
    font: float = 1.0

    def sp(self, value: float) -> int:
        """Boşluk/boyut (mantıksal px). Windows DPI ölçeklemesini Qt kendisi uygular."""
        return max(1, round(value * self.spacing))

    def fs(self, value: float) -> int:
        """Yazı boyutu (px)."""
        return max(8, round(value * self.font))
