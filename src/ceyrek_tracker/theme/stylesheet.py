"""Tema belirteçlerinden Qt stil sayfası (QSS) üretir.

Widget'lar yalnızca `role` özelliğini (ör. `label.setProperty("role", "dim")`) ve
nesne adını bilir; renk ve boyut kararları burada, tek yerde verilir.
"""

from __future__ import annotations

from ceyrek_tracker.theme.tokens import ICON_FONT, UI_FONT, Metrics, Theme, rgba


def build_stylesheet(theme: Theme, metrics: Metrics) -> str:
    t, m = theme, metrics
    return f"""
QLabel {{
    background: transparent;
    color: {t.text};
    font-family: {UI_FONT};
    font-size: {m.fs(13)}px;
}}
QLabel[role="dim"] {{ color: {t.text_dim}; font-size: {m.fs(11)}px; }}
QLabel[role="soft"] {{ color: {t.text_soft}; font-size: {m.fs(12)}px; }}
QLabel[role="title"] {{ color: {t.text_dim}; font-size: {m.fs(12)}px; }}
QLabel[role="accent"] {{ color: {t.accent}; font-size: {m.fs(12)}px; }}
QLabel[role="header"] {{ color: {t.text_dim}; font-size: {m.fs(11)}px; }}
QLabel[role="header_date"] {{ color: {t.text_soft}; font-size: {m.fs(12)}px; }}
QLabel[role="clock"] {{ font-size: {m.fs(44)}px; font-weight: 400; }}
QLabel[role="big"] {{ font-size: {m.fs(28)}px; font-weight: 500; }}
QLabel[role="value"] {{ font-size: {m.fs(13)}px; font-weight: 500; }}
QLabel[role="up"] {{ color: {t.up}; }}
QLabel[role="down"] {{ color: {t.down}; }}
QLabel[role="warn"] {{ color: {t.warn}; }}
QLabel[role="error"] {{ color: {t.down}; font-size: {m.fs(12)}px; }}
QLabel[role="icon"] {{
    color: {t.text_dim};
    font-family: '{ICON_FONT}';
    font-size: {m.fs(13)}px;
}}
QLabel[role="icon"][accent="true"] {{ color: {t.accent}; }}

QFrame[role="inner"] {{
    background: {t.surface};
    border: 1px solid {t.border};
    border-radius: {t.radius_card}px;
}}
QFrame[role="tile"] {{
    background: {t.surface};
    border: none;
    border-radius: {t.radius_small}px;
}}
QFrame[role="divider"] {{
    background: {t.border};
    border: none;
    max-height: 1px;
    min-height: 1px;
}}

QToolButton[role="icon"] {{
    background: transparent;
    border: none;
    border-radius: {t.radius_small}px;
    color: {t.text_dim};
    font-family: '{ICON_FONT}';
    font-size: {m.fs(13)}px;
    padding: {m.sp(3)}px;
}}
QToolButton[role="icon"]:hover {{ background: {t.surface_hover}; color: {t.text}; }}
QToolButton[role="icon"][active="true"] {{ color: {t.accent}; }}

QFrame[role="card_header"] {{ background: transparent; border: none; }}
QFrame[role="card_header"]:hover QLabel[role="title"] {{ color: {t.text_soft}; }}

QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{
    background: transparent;
    width: {m.sp(6)}px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: transparent;
    border-radius: {m.sp(2)}px;
    min-height: {m.sp(28)}px;
}}
QScrollArea[hover="true"] QScrollBar::handle:vertical {{ background: {rgba(t.ink, 0.28)}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}

QMenu {{
    background: {t.bg};
    color: {t.text};
    border: 1px solid {t.border};
    border-radius: {t.radius_small}px;
    font-family: {UI_FONT};
    font-size: {m.fs(12)}px;
    padding: {m.sp(4)}px;
}}
QMenu::item {{
    padding: {m.sp(5)}px {m.sp(18)}px {m.sp(5)}px {m.sp(22)}px;
    border-radius: {t.radius_small}px;
}}
QMenu::item:selected {{ background: {t.surface_hover}; }}
QMenu::indicator {{
    width: {m.sp(6)}px;
    height: {m.sp(6)}px;
    border-radius: {m.sp(3)}px;
    left: {m.sp(8)}px;
}}
QMenu::indicator:checked {{ background: {t.accent}; }}

QToolTip {{
    background: {t.bg};
    color: {t.text};
    border: 1px solid {t.border};
    font-family: {UI_FONT};
    padding: {m.sp(4)}px;
}}
"""
