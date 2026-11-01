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
    symbol: str  # satır simgesi: para simgesi (yazı) ya da çizim adı (bkz. icon.py)
    currency: str = "TRY"


INSTRUMENTS: tuple[Instrument, ...] = (
    Instrument("usd", "Dolar (USD)", "$"),
    Instrument("eur", "Euro (EUR)", "€"),
    Instrument("gbp", "Sterlin (GBP)", "£"),
    Instrument("chf", "İsviçre Frangı (CHF)", "Fr"),
    Instrument("gram", "Gram Altın", "bar"),
    Instrument("gram_has", "Has Altın (gr)", "bar"),
    Instrument("ceyrek", "Çeyrek Altın", "coin"),
    Instrument("yarim", "Yarım Altın", "coin"),
    Instrument("tam", "Tam Altın", "coin"),
    Instrument("cumhuriyet", "Cumhuriyet Altını", "coin"),
    Instrument("ata", "Ata Altın", "coin"),
    Instrument("resat", "Reşat Altın", "coin"),
    Instrument("hamit", "Hamit Altın", "coin"),
    Instrument("ikibucuk", "İkibuçuk Altın", "coin"),
    Instrument("gremse", "Gremse Altın", "coin"),
    Instrument("besli", "Beşli Altın", "coin"),
    Instrument("ayar14", "14 Ayar (gr)", "ring"),
    Instrument("ayar18", "18 Ayar (gr)", "ring"),
    Instrument("bilezik22", "22 Ayar Bilezik (gr)", "ring"),
    Instrument("ons", "Ons Altın", "weight", currency="USD"),
    Instrument("gumus", "Gümüş (gr)", "gem"),
)

_BY_ID: dict[str, Instrument] = {i.id: i for i in INSTRUMENTS}

# Kartta varsayılan olarak gösterilenler (sıra = görünüm sırası).
DEFAULT_ITEMS: tuple[str, ...] = ("usd", "eur", "gbp", "gram", "ceyrek", "gumus", "ons")


def get_instrument(type_id: str) -> Instrument | None:
    return _BY_ID.get(type_id)
