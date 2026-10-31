"""Uygulamanın tanıdığı finans enstrümanları: döviz, altın ve gümüş.

Her kaynak kendi anahtarlarını kullanır; sağlayıcılar bu kataloğun `id` alanına
eşleme yapar. Böylece arayüz ve ayarlar kaynaktan bağımsız kalır.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Instrument:
    id: str
    name: str
    symbol: str  # satır rozetindeki yazı: para simgesi ya da element simgesi
    currency: str = "TRY"


INSTRUMENTS: tuple[Instrument, ...] = (
    Instrument("usd", "Dolar (USD)", "$"),
    Instrument("eur", "Euro (EUR)", "€"),
    Instrument("gbp", "Sterlin (GBP)", "£"),
    Instrument("chf", "İsviçre Frangı (CHF)", "Fr"),
    Instrument("gram", "Gram Altın", "Au"),
    Instrument("gram_has", "Has Altın (gr)", "Au"),
    Instrument("ceyrek", "Çeyrek Altın", "Au"),
    Instrument("yarim", "Yarım Altın", "Au"),
    Instrument("tam", "Tam Altın", "Au"),
    Instrument("cumhuriyet", "Cumhuriyet Altını", "Au"),
    Instrument("ata", "Ata Altın", "Au"),
    Instrument("resat", "Reşat Altın", "Au"),
    Instrument("hamit", "Hamit Altın", "Au"),
    Instrument("ikibucuk", "İkibuçuk Altın", "Au"),
    Instrument("gremse", "Gremse Altın", "Au"),
    Instrument("besli", "Beşli Altın", "Au"),
    Instrument("ayar14", "14 Ayar (gr)", "Au"),
    Instrument("ayar18", "18 Ayar (gr)", "Au"),
    Instrument("bilezik22", "22 Ayar Bilezik (gr)", "Au"),
    Instrument("ons", "Ons Altın", "Au", currency="USD"),
    Instrument("gumus", "Gümüş (gr)", "Ag"),
)

_BY_ID: dict[str, Instrument] = {i.id: i for i in INSTRUMENTS}

# Kartta varsayılan olarak gösterilenler (sıra = görünüm sırası).
DEFAULT_ITEMS: tuple[str, ...] = ("usd", "eur", "gbp", "gram", "ceyrek", "gumus", "ons")


def get_instrument(type_id: str) -> Instrument | None:
    return _BY_ID.get(type_id)
