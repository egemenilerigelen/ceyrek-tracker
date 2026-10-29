"""Truncgil Finans ücretsiz API'si (anahtar gerektirmez).

`v3` uç noktası kullanılıyor: Truncgil'in `today.json` ve `v4` uç noktaları
yanıtı sık sık yarıda kesiyor, `v3` ise tutarlı tam yanıt veriyor.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import requests

from ceyrek_tracker.domain.formatting import parse_tr_number
from ceyrek_tracker.domain.models import Quote, Snapshot
from ceyrek_tracker.providers.base import ProviderError, create_session, get_json

logger = logging.getLogger(__name__)

URL = "https://finans.truncgil.com/v3/today.json"

# katalog id -> Truncgil anahtarı
KEY_MAP: dict[str, str] = {
    "gram": "gram-altin",
    "gram_has": "gram-has-altin",
    "ceyrek": "ceyrek-altin",
    "yarim": "yarim-altin",
    "tam": "tam-altin",
    "cumhuriyet": "cumhuriyet-altini",
    "ata": "ata-altin",
    "resat": "resat-altin",
    "hamit": "hamit-altin",
    "ikibucuk": "ikibucuk-altin",
    "gremse": "gremse-altin",
    "besli": "besli-altin",
    "ayar14": "14-ayar-altin",
    "ayar18": "18-ayar-altin",
    "bilezik22": "22-ayar-bilezik",
    "ons": "ons",
}


def parse(payload: Any, fetched_at: datetime) -> Snapshot:
    if not isinstance(payload, dict):
        raise ProviderError("Truncgil: beklenmeyen yanıt biçimi")

    quotes: dict[str, Quote] = {}
    for type_id, key in KEY_MAP.items():
        item = payload.get(key)
        if not isinstance(item, dict):
            continue
        try:
            change_raw = item.get("Change")
            quotes[type_id] = Quote(
                type_id=type_id,
                buy=parse_tr_number(item["Buying"]),
                sell=parse_tr_number(item["Selling"]),
                change_pct=parse_tr_number(change_raw) if change_raw else None,
            )
        except (KeyError, ValueError) as exc:
            logger.warning("Truncgil '%s' ayrıştırılamadı: %r", key, exc)

    if not quotes:
        raise ProviderError("Truncgil: yanıtta altın verisi yok")

    source_time = None
    if raw_time := payload.get("Update_Date"):
        try:
            source_time = datetime.strptime(raw_time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            logger.warning("Truncgil tarih biçimi tanınmadı: %r", raw_time)

    return Snapshot(
        source_id=TruncgilProvider.id,
        source_name=TruncgilProvider.name,
        quotes=quotes,
        fetched_at=fetched_at,
        source_time=source_time,
    )


class TruncgilProvider:
    id = "truncgil"
    name = "Truncgil"

    def __init__(self, session: requests.Session | None = None) -> None:
        self._session = session or create_session()

    def fetch(self) -> Snapshot:
        return parse(get_json(self._session, URL), fetched_at=datetime.now())
