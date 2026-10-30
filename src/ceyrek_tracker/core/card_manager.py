"""Kartların kaydı, sırası ve yaşam döngüsü."""

from __future__ import annotations

import logging
from collections.abc import Sequence

from PySide6.QtCore import QObject, Signal

from ceyrek_tracker.core.card_base import CardContext, CardSpec
from ceyrek_tracker.core.card_host import CardHost
from ceyrek_tracker.core.settings import CardSetting
from ceyrek_tracker.theme import Look

logger = logging.getLogger(__name__)


def reconcile(specs: Sequence[CardSpec], saved: Sequence[CardSetting]) -> list[CardSetting]:
    """Kayıtlı kart ayarlarını mevcut kartlarla eşler.

    Kayıtlı sıra korunur, artık var olmayan kartlar atılır, yeni kartlar sona eklenir.
    """
    by_id = {s.id: s for s in specs}
    result = [c for c in saved if c.id in by_id]
    known = {c.id for c in result}
    result += [CardSetting(s.id, enabled=s.default_enabled) for s in specs if s.id not in known]
    return result


class CardManager(QObject):
    collapsed_changed = Signal(str, bool)
    config_changed = Signal(str, object)

    def __init__(
        self,
        specs: Sequence[CardSpec],
        saved: Sequence[CardSetting],
        look: Look,
        animate: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._specs = {s.id: s for s in specs}
        self.settings = reconcile(specs, saved)
        self.hosts: list[CardHost] = []
        for setting in self.settings:
            if setting.enabled:
                self.hosts.append(self._build(self._specs[setting.id], setting, look, animate))

    def _build(self, spec: CardSpec, setting: CardSetting, look: Look, animate: bool) -> CardHost:
        card = None
        error = ""
        try:
            card = spec.factory(CardContext(look=look, config=dict(setting.config)))
        except Exception:
            # Bir kartın kurulamaması diğerlerini ve paneli etkilemesin.
            logger.exception("Kart '%s' oluşturulamadı", spec.id)
            error = "Bu kart başlatılamadı. Ayrıntılar log dosyasında."
        if card is not None:
            card.config_changed.connect(
                lambda config, card_id=spec.id: self.config_changed.emit(card_id, config)
            )
        host = CardHost(spec, card, look, setting.collapsed, animate, error)
        host.collapsed_changed.connect(self.collapsed_changed)
        return host

    def card_settings(self) -> tuple[CardSetting, ...]:
        return tuple(self.settings)

    def set_collapsed(self, card_id: str, collapsed: bool) -> None:
        self.settings = [
            CardSetting(c.id, c.enabled, collapsed, c.config) if c.id == card_id else c
            for c in self.settings
        ]

    def set_config(self, card_id: str, config: dict) -> None:
        self.settings = [
            CardSetting(c.id, c.enabled, c.collapsed, dict(config)) if c.id == card_id else c
            for c in self.settings
        ]

    def show_all(self) -> None:
        for host in self.hosts:
            host.card_shown()

    def hide_all(self) -> None:
        for host in self.hosts:
            host.card_hidden()

    def set_look(self, look: Look) -> None:
        for host in self.hosts:
            host.set_look(look)

    def shutdown(self) -> None:
        for host in self.hosts:
            host.shutdown()
