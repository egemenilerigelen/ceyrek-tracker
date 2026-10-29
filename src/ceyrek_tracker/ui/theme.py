"""Renkler, yazı tipleri ve stil sayfası. Arayüzdeki tüm görsel değerler buradan gelir.

Kimlik: sıcak, koyu bir zemin üzerinde altın vurgu. Rakamlar Bahnschrift ile
(Windows 10+ ile gelir) yazılır; dar ve okunaklı olduğu için fiyat sütunlarında
hizayı korur.
"""

from __future__ import annotations

from ceyrek_tracker.domain.models import FeedStatus, Trend

UI_FONT = "'Segoe UI Variable Text', 'Segoe UI', sans-serif"
NUMBER_FONT = "'Bahnschrift', 'Segoe UI', sans-serif"

BG_TOP = "#1c1913"
BG_BOTTOM = "#0f0d0a"
SURFACE = "#1a1712"
GOLD = "#e3b950"
GOLD_SOFT = "rgba(227, 185, 80, 0.16)"
HAIRLINE = "rgba(227, 185, 80, 0.14)"

TEXT_PRIMARY = "#f6f1e7"
TEXT_SECONDARY = "#cfc6b6"
TEXT_MUTED = "#8c8476"
TEXT_DIM = "#5b544a"
UP = "#5fcf92"
DOWN = "#f07a6e"

TREND_COLORS: dict[Trend, str] = {
    Trend.UP: UP,
    Trend.DOWN: DOWN,
    Trend.FLAT: TEXT_PRIMARY,
    Trend.UNKNOWN: TEXT_PRIMARY,
}

# Durum rozeti: (metin, renk)
STATUS_BADGES: dict[FeedStatus, tuple[str, str]] = {
    FeedStatus.LIVE: ("CANLI", UP),
    FeedStatus.STALE: ("GECİKMELİ", "#e8a53c"),
    FeedStatus.LOADING: ("BAĞLANIYOR", TEXT_MUTED),
    FeedStatus.OFFLINE: ("BAĞLANTI YOK", DOWN),
}


def rgba(hex_color: str, alpha: float) -> str:
    """'#rrggbb' -> 'rgba(r, g, b, a)'; Qt stil sayfasında saydamlık için."""
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r}, {g}, {b}, {alpha})"


def change_color(change_pct: float | None) -> str:
    if change_pct is None or change_pct == 0:
        return TEXT_MUTED
    return UP if change_pct > 0 else DOWN


def price_style(color: str) -> str:
    return f"font-family: {NUMBER_FONT}; font-size: 24px; font-weight: 600; color: {color};"


STYLESHEET = f"""
QWidget#root {{
    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 {BG_TOP}, stop: 1 {BG_BOTTOM});
    border: 1px solid {HAIRLINE};
    border-radius: 14px;
}}
QLabel {{
    background: transparent;
    font-family: {UI_FONT};
    color: {TEXT_SECONDARY};
}}
QLabel#featured_name {{
    font-size: 12px;
    font-weight: 600;
    color: {GOLD};
    letter-spacing: 0.5px;
}}
QLabel.caption {{
    font-size: 10px;
    color: {TEXT_MUTED};
}}
QLabel#change_line {{
    font-size: 11px;
}}
QLabel#status_line {{
    font-size: 10px;
    color: {TEXT_MUTED};
}}

QPushButton.nav {{
    background: transparent;
    color: {TEXT_MUTED};
    font-family: {UI_FONT};
    font-size: 12px;
    border: none;
    border-radius: 9px;
    padding: 0;
}}
QPushButton.nav:hover {{ background: {GOLD_SOFT}; color: {TEXT_PRIMARY}; }}
QPushButton#close_btn:hover {{ background: {rgba(DOWN, 0.2)}; color: {DOWN}; }}

QWidget#list_divider {{
    background: {HAIRLINE};
}}
QWidget.price_row {{
    border-radius: 6px;
}}
QWidget.price_row:hover {{
    background: {GOLD_SOFT};
}}
QLabel.row_name {{ font-size: 11px; color: {TEXT_SECONDARY}; }}
QLabel.row_featured {{ color: {GOLD}; font-weight: 600; }}
QLabel.row_value {{ font-family: {NUMBER_FONT}; font-size: 12px; }}
QLabel.row_change {{ font-family: {NUMBER_FONT}; font-size: 11px; }}

QMenu {{
    background: {SURFACE};
    color: {TEXT_SECONDARY};
    border: 1px solid {HAIRLINE};
    border-radius: 8px;
    padding: 5px;
    font-family: {UI_FONT};
    font-size: 12px;
}}
QMenu::item {{ padding: 5px 24px 5px 24px; border-radius: 5px; }}
QMenu::item:selected {{ background: {GOLD_SOFT}; color: {TEXT_PRIMARY}; }}
QMenu::item:disabled {{ color: {TEXT_DIM}; }}
QMenu::separator {{ height: 1px; background: {HAIRLINE}; margin: 5px 8px; }}
QToolTip {{
    background: {SURFACE};
    color: {TEXT_SECONDARY};
    border: 1px solid {HAIRLINE};
    font-family: {UI_FONT};
}}
"""
