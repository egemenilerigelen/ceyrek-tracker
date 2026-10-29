"""Kullanıcı ayarları: tanımlar, doğrulama ve kalıcı saklama."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

from ceyrek_tracker.domain.catalog import DEFAULT_FEATURED, GOLD_TYPES, is_known
from ceyrek_tracker.providers import DEFAULT_PROVIDER, PROVIDER_CHOICES
from ceyrek_tracker.storage import read_json, write_json

logger = logging.getLogger(__name__)

# Menüde sunulan yenileme aralıkları (saniye, etiket)
REFRESH_CHOICES: tuple[tuple[int, str], ...] = (
    (30, "30 saniye"),
    (60, "1 dakika"),
    (120, "2 dakika"),
    (300, "5 dakika"),
    (900, "15 dakika"),
)
DEFAULT_REFRESH = 60
MIN_REFRESH = 30

_PROVIDER_IDS = {pid for pid, _ in PROVIDER_CHOICES}


def _default_visible() -> tuple[str, ...]:
    return tuple(g.id for g in GOLD_TYPES)


@dataclass(frozen=True)
class Settings:
    provider: str = DEFAULT_PROVIDER
    refresh_seconds: int = DEFAULT_REFRESH
    featured: str = DEFAULT_FEATURED
    visible: tuple[str, ...] = field(default_factory=_default_visible)
    expanded: bool = False
    always_on_top: bool = False
    window_pos: tuple[int, int] | None = None

    def with_changes(self, **changes: Any) -> Settings:
        return replace(self, **changes)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["visible"] = list(self.visible)
        data["window_pos"] = list(self.window_pos) if self.window_pos else None
        return data

    @classmethod
    def from_dict(cls, data: Any) -> Settings:
        """Bozuk ya da tanınmayan değerleri varsayılana çekerek okur."""
        default = cls()
        if not isinstance(data, dict):
            return default

        provider = data.get("provider")
        if provider not in _PROVIDER_IDS:
            provider = default.provider

        refresh = data.get("refresh_seconds")
        if not isinstance(refresh, int) or isinstance(refresh, bool) or refresh < MIN_REFRESH:
            refresh = default.refresh_seconds

        featured = data.get("featured")
        if not isinstance(featured, str) or not is_known(featured):
            featured = default.featured

        visible_raw = data.get("visible")
        if isinstance(visible_raw, list):
            visible = tuple(
                v for v in dict.fromkeys(visible_raw) if isinstance(v, str) and is_known(v)
            )
        else:
            visible = default.visible

        pos = data.get("window_pos")
        window_pos = None
        if isinstance(pos, list | tuple) and len(pos) == 2 and all(isinstance(v, int) for v in pos):
            window_pos = (pos[0], pos[1])

        return cls(
            provider=provider,
            refresh_seconds=refresh,
            featured=featured,
            visible=visible,
            expanded=bool(data.get("expanded", default.expanded)),
            always_on_top=bool(data.get("always_on_top", default.always_on_top)),
            window_pos=window_pos,
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
