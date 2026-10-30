"""Fiyat sağlayıcılarının ortak arayüzü."""

from __future__ import annotations

from typing import Protocol

from ceyrek_tracker.cards.finance.models import Snapshot


class PriceProvider(Protocol):
    id: str
    name: str

    def fetch(self) -> Snapshot: ...
