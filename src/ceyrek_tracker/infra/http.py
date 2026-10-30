"""HTTP yardımcıları: yeniden denemeli oturum, bozuk yanıta dayanıklı JSON çekme.

Her veri kaynağı (hava, finans...) aynı yardımcıları ve hata türünü kullanır; kartlar
birbirinin paketine bağımlı olmaz.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ceyrek_tracker import __version__

logger = logging.getLogger(__name__)

USER_AGENT = f"CeyrekTakip/{__version__} (+https://github.com/egemenilerigelen/ceyrek-tracker)"
# (bağlantı, okuma) zaman aşımı, saniye
DEFAULT_TIMEOUT = (5, 10)


class ProviderError(Exception):
    """Bir veri kaynağından geçerli veri alınamadığında fırlatılır."""


def create_session() -> requests.Session:
    """Geçici ağ hatalarında (kopma, 5xx, 429) kendiliğinden yeniden deneyen oturum."""
    retry = Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})
    return session


def get_json(session: requests.Session, url: str, attempts: int = 3) -> Any:
    """URL'den JSON çeker.

    Bazı ücretsiz kaynaklar gövdeyi zaman zaman yarıda kesiyor (HTTP 200 dönüp
    eksik JSON gönderiyor). Bu durumda isteği birkaç kez tekrarlıyoruz.
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            return json.loads(response.content)
        except ValueError as exc:
            last_error = exc
            logger.warning("%s bozuk/eksik JSON döndü (deneme %d/%d)", url, attempt, attempts)
        except requests.RequestException as exc:
            raise ProviderError(f"Bağlantı hatası: {exc.__class__.__name__}") from exc
    raise ProviderError("Kaynak eksik veya bozuk yanıt döndürdü") from last_error
