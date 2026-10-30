"""Altınkaynak'ın sitesinde kullandığı herkese açık fiyat listesi.

Güncelleme sıklığı yüksek (saniyeler mertebesinde) ama günlük değişim yüzdesi
vermiyor. Resmi bir geliştirici API'si değil; yedek kaynak olarak kullanılıyor.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import datetime
from typing import Any

import requests

from ceyrek_tracker.cards.finance.formatting import parse_tr_number
from ceyrek_tracker.cards.finance.models import Quote, Snapshot
from ceyrek_tracker.infra.http import ProviderError, create_session, get_json

logger = logging.getLogger(__name__)

URL = "https://static.altinkaynak.com/public/Gold"

# katalog id -> Altınkaynak "Kod" alanı. Karşılığı olmayan türler (cumhuriyet,
# ikibuçuk) bu kaynakta boş görünür.
CODE_MAP: dict[str, str] = {
    "gram": "GA",
    "gram_has": "HH_T",
    "ceyrek": "C",
    "yarim": "Y",
    "tam": "T",
    "ata": "PA",
    "resat": "R",
    "hamit": "H",
    "gremse": "G",
    "besli": "A5",
    "ayar14": "14",
    "ayar18": "18",
    "bilezik22": "PB",
    "ons": "XAUUSD",
}


def parse(payload: Any, fetched_at: datetime) -> Snapshot:
    if not isinstance(payload, list):
        raise ProviderError("Altınkaynak: beklenmeyen yanıt biçimi")

    by_code = {item.get("Kod"): item for item in payload if isinstance(item, dict)}
    quotes: dict[str, Quote] = {}
    times: list[datetime] = []
    for type_id, code in CODE_MAP.items():
        item = by_code.get(code)
        if item is None:
            continue
        try:
            quotes[type_id] = Quote(
                type_id=type_id,
                buy=parse_tr_number(item["Alis"]),
                sell=parse_tr_number(item["Satis"]),
            )
        except (KeyError, ValueError) as exc:
            logger.warning("Altınkaynak '%s' ayrıştırılamadı: %r", code, exc)
            continue
        with contextlib.suppress(KeyError, ValueError):
            times.append(datetime.strptime(item["GuncellenmeZamani"], "%d.%m.%Y %H:%M:%S"))

    if not quotes:
        raise ProviderError("Altınkaynak: yanıtta altın verisi yok")

    return Snapshot(
        source_id=AltinkaynakProvider.id,
        source_name=AltinkaynakProvider.name,
        quotes=quotes,
        fetched_at=fetched_at,
        source_time=max(times) if times else None,
    )


class AltinkaynakProvider:
    id = "altinkaynak"
    name = "Altınkaynak"

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or create_session()

    def fetch(self) -> Snapshot:
        return parse(get_json(self._session, URL), fetched_at=datetime.now())
