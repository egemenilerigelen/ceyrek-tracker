"""Uygulamanın tanıdığı altın türleri.

Her kaynak kendi anahtarlarını kullanır; sağlayıcılar bu kataloğun `id` alanına
eşleme yapar. Böylece arayüz ve ayarlar kaynaktan bağımsız kalır.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoldType:
    id: str
    name: str
    currency: str = "TRY"


GOLD_TYPES: tuple[GoldType, ...] = (
    GoldType("gram", "Gram Altın"),
    GoldType("gram_has", "Has Altın (gr)"),
    GoldType("ceyrek", "Çeyrek Altın"),
    GoldType("yarim", "Yarım Altın"),
    GoldType("tam", "Tam Altın"),
    GoldType("cumhuriyet", "Cumhuriyet Altını"),
    GoldType("ata", "Ata Altın"),
    GoldType("resat", "Reşat Altın"),
    GoldType("hamit", "Hamit Altın"),
    GoldType("ikibucuk", "İkibuçuk Altın"),
    GoldType("gremse", "Gremse Altın"),
    GoldType("besli", "Beşli Altın"),
    GoldType("ayar14", "14 Ayar (gr)"),
    GoldType("ayar18", "18 Ayar (gr)"),
    GoldType("bilezik22", "22 Ayar Bilezik (gr)"),
    GoldType("ons", "Ons Altın", currency="USD"),
)

_BY_ID: dict[str, GoldType] = {g.id: g for g in GOLD_TYPES}

DEFAULT_FEATURED = "ceyrek"


def get_gold_type(type_id: str) -> GoldType | None:
    return _BY_ID.get(type_id)


def is_known(type_id: str) -> bool:
    return type_id in _BY_ID
