"""Kart kayıt defteri. Yeni kart: modülünü yaz, `SPEC`'ini buraya ekle (sıra = varsayılan sıra)."""

from __future__ import annotations

from ceyrek_tracker.cards import clipboard, finance, spotify, weather
from ceyrek_tracker.core.card_base import CardSpec

CARDS: tuple[CardSpec, ...] = (weather.SPEC, finance.SPEC, spotify.SPEC, clipboard.SPEC)
