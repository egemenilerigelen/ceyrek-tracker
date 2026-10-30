"""Kullanıcı ayarları: tek bir settings.json, doğrulama ve kalıcı saklama.

Bozuk ya da tanınmayan her değer sessizce varsayılana çekilir; elle düzenlenen bir
dosya yüzünden uygulama açılmaz hale gelmez.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from ceyrek_tracker.infra.storage import read_json, write_json
from ceyrek_tracker.theme import Look, resolve_look
from ceyrek_tracker.theme.tokens import DENSITIES, THEMES

logger = logging.getLogger(__name__)

OPEN_MODES = ("hover", "click")
SCREEN_MODES = ("cursor", "primary")
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class CardSetting:
    """Bir kartın kullanıcı ayarı: açık mı, katlı mı ve karta özel yapılandırma."""

    id: str
    enabled: bool = True
    collapsed: bool = False
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "enabled": self.enabled,
            "collapsed": self.collapsed,
            "config": dict(self.config),
        }

    @classmethod
    def from_dict(cls, data: Any) -> CardSetting | None:
        if not isinstance(data, dict) or not isinstance(data.get("id"), str):
            return None
        config = data.get("config")
        return cls(
            id=data["id"],
            enabled=bool(data.get("enabled", True)),
            collapsed=bool(data.get("collapsed", False)),
            config=config if isinstance(config, dict) else {},
        )


def _choice(data: dict, key: str, choices, default):
    value = data.get(key)
    return value if value in choices else default


def _number(data: dict, key: str, low: float, high: float, default):
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return default
    if not low <= value <= high:
        return default
    return type(default)(value)


def _flag(data: dict, key: str, default: bool) -> bool:
    value = data.get(key)
    return value if isinstance(value, bool) else default


@dataclass(frozen=True)
class Settings:
    # Panelin açılış/kapanış davranışı
    open_mode: str = "hover"  # hover: üzerine gelince, click: yalnızca tıklayınca
    hover_delay_ms: int = 200
    close_on_outside_click: bool = True
    leave_close_seconds: float = 3.0  # panelden ayrıldıktan sonra kapanma; 0 = kapalı
    pinned: bool = False
    animations: bool = True
    animation_ms: int = 220
    panel_width: int = 310
    # Kısayol ve ekran seçimi
    hotkey: str = "win+alt+p"  # boş = kısayol yok
    hotkey_screen: str = "cursor"
    trigger_screen: str = "primary"  # "primary" ya da ekran adı (ör. \\.\DISPLAY2)
    # Tetikleyici (sağ kenardaki tutamaç)
    trigger_kind: str = "handle"
    handle_thickness: int = 6
    handle_length: int = 96
    handle_position: float = 0.5  # 0 = üst, 1 = alt
    # Görünüm
    theme: str = "dark"
    accent: str | None = None
    density: str = "normal"
    font_scale: float = 1.0
    blur: bool = True
    glass_opacity: float = 0.80
    cards: tuple[CardSetting, ...] = ()

    def with_changes(self, **changes: Any) -> Settings:
        return replace(self, **changes)

    def card(self, card_id: str) -> CardSetting | None:
        return next((c for c in self.cards if c.id == card_id), None)

    def with_card(self, card: CardSetting) -> Settings:
        """Kartı aynı sırada günceller; yoksa sona ekler."""
        cards = [card if c.id == card.id else c for c in self.cards]
        if card.id not in {c.id for c in self.cards}:
            cards.append(card)
        return replace(self, cards=tuple(cards))

    def to_dict(self) -> dict[str, Any]:
        data = {k: getattr(self, k) for k in self.__dataclass_fields__ if k != "cards"}
        data["cards"] = [c.to_dict() for c in self.cards]
        return data

    @classmethod
    def from_dict(cls, data: Any) -> Settings:
        d = cls()
        if not isinstance(data, dict):
            return d

        accent = data.get("accent")
        if not (isinstance(accent, str) and _HEX_COLOR.match(accent)):
            accent = None

        cards: list[CardSetting] = []
        seen: set[str] = set()
        for raw in data.get("cards") if isinstance(data.get("cards"), list) else []:
            card = CardSetting.from_dict(raw)
            if card and card.id not in seen:
                seen.add(card.id)
                cards.append(card)

        trigger_screen = data.get("trigger_screen")
        if not (isinstance(trigger_screen, str) and trigger_screen):
            trigger_screen = d.trigger_screen
        hotkey = data.get("hotkey")
        if not isinstance(hotkey, str):
            hotkey = d.hotkey

        return cls(
            open_mode=_choice(data, "open_mode", OPEN_MODES, d.open_mode),
            hover_delay_ms=_number(data, "hover_delay_ms", 0, 3000, d.hover_delay_ms),
            close_on_outside_click=_flag(data, "close_on_outside_click", d.close_on_outside_click),
            leave_close_seconds=_number(data, "leave_close_seconds", 0, 60, d.leave_close_seconds),
            pinned=_flag(data, "pinned", d.pinned),
            animations=_flag(data, "animations", d.animations),
            animation_ms=_number(data, "animation_ms", 50, 1000, d.animation_ms),
            panel_width=_number(data, "panel_width", 260, 640, d.panel_width),
            hotkey=hotkey.strip().lower(),
            hotkey_screen=_choice(data, "hotkey_screen", SCREEN_MODES, d.hotkey_screen),
            trigger_screen=trigger_screen,
            trigger_kind=data["trigger_kind"]
            if isinstance(data.get("trigger_kind"), str)
            else d.trigger_kind,
            handle_thickness=_number(data, "handle_thickness", 2, 24, d.handle_thickness),
            handle_length=_number(data, "handle_length", 24, 600, d.handle_length),
            handle_position=_number(data, "handle_position", 0.0, 1.0, d.handle_position),
            theme=_choice(data, "theme", tuple(THEMES), d.theme),
            accent=accent,
            density=_choice(data, "density", tuple(DENSITIES), d.density),
            font_scale=_number(data, "font_scale", 0.8, 1.6, d.font_scale),
            blur=_flag(data, "blur", d.blur),
            glass_opacity=_number(data, "glass_opacity", 0.3, 1.0, d.glass_opacity),
            cards=tuple(cards),
        )


class SettingsStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> Settings:
        return Settings.from_dict(read_json(self.path))

    def save(self, settings: Settings) -> None:
        try:
            write_json(self.path, settings.to_dict())
        except OSError as exc:
            logger.warning("Ayarlar kaydedilemedi: %s", exc)


def look_from_settings(settings: Settings) -> Look:
    """Ayarlardaki tema alanlarından görünümü (renk, boyut, cam) üretir."""
    return resolve_look(
        settings.theme,
        settings.density,
        settings.font_scale,
        accent=settings.accent,
        glass_opacity=settings.glass_opacity,
        blur=settings.blur,
    )
