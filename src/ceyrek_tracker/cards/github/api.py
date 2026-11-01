"""GitHub katkı tablosu: herkese açık profil sayfasının katkı parçası (hesap ya da token gerekmez).

`https://github.com/users/<ad>/contributions` her gün için bir `<td data-date data-level>`
hücresi ve hücreye `for` ile bağlı bir ipucu (`<tool-tip>`: "3 contributions on May 5th.")
döndürür. Resmi bir API olmadığı için biçim değişirse `ProviderError` fırlatılır ve kart
önbellekteki tabloyu göstermeye devam eder.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from html.parser import HTMLParser

import requests

from ceyrek_tracker.cards.github.models import MAX_LEVEL, ContributionDay, Contributions
from ceyrek_tracker.infra.http import DEFAULT_TIMEOUT, ProviderError

URL = "https://github.com/users/{username}/contributions"
# GitHub ipucu metnini Accept-Language'e göre yerelleştirir; ayrıştırma İngilizceye dayanır.
HEADERS = {"Accept": "text/html", "Accept-Language": "en-US,en;q=0.9"}
_COUNT = re.compile(r"^(\d+) contributions? on ")
_USERNAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")


class _CalendarParser(HTMLParser):
    """Hücreleri (`id -> (tarih, seviye)`) ve ipuçlarını (`hücre id -> metin`) toplar."""

    def __init__(self) -> None:
        super().__init__()
        self.cells: dict[str, tuple[str, str]] = {}
        self.tips: dict[str, str] = {}
        self._tip_for: str | None = None
        self._tip_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: v or "" for k, v in attrs}
        if tag == "td" and a.get("data-date") and "data-level" in a:
            self.cells[a.get("id", a["data-date"])] = (a["data-date"], a["data-level"])
        elif tag == "tool-tip" and a.get("for"):
            self._tip_for, self._tip_text = a["for"], []

    def handle_data(self, data: str) -> None:
        if self._tip_for is not None:
            self._tip_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "tool-tip" and self._tip_for is not None:
            self.tips[self._tip_for] = " ".join("".join(self._tip_text).split())
            self._tip_for = None


def _count(tip: str) -> int:
    if tip.startswith("No contributions on "):
        return 0
    match = _COUNT.match(tip)
    if match is None:
        raise ProviderError("Katkı tablosunun biçimi anlaşılamadı")
    return int(match[1])


def parse_contributions(html: str, username: str, fetched_at: datetime) -> Contributions:
    parser = _CalendarParser()
    parser.feed(html)
    days: list[ContributionDay] = []
    try:
        for cell_id, (raw_day, raw_level) in parser.cells.items():
            tip = parser.tips.get(cell_id)
            if tip is None:
                raise ProviderError("Katkı tablosunun biçimi anlaşılamadı")
            level = int(raw_level)
            if not 0 <= level <= MAX_LEVEL:
                raise ProviderError("Katkı tablosunun biçimi anlaşılamadı")
            days.append(ContributionDay(date.fromisoformat(raw_day), _count(tip), level))
    except ValueError as exc:
        raise ProviderError("Katkı tablosunun biçimi anlaşılamadı") from exc
    if not days:
        raise ProviderError("Katkı tablosu bulunamadı")
    days.sort(key=lambda d: d.day)
    return Contributions(username, tuple(days), fetched_at)


def fetch_contributions(session: requests.Session, username: str) -> Contributions:
    if not _USERNAME.match(username):
        raise ProviderError(f"Geçersiz GitHub kullanıcı adı: {username!r}")
    try:
        response = session.get(
            URL.format(username=username), headers=HEADERS, timeout=DEFAULT_TIMEOUT
        )
    except requests.RequestException as exc:
        raise ProviderError(f"Bağlantı hatası: {exc.__class__.__name__}") from exc
    if response.status_code == 404:
        raise ProviderError(f"GitHub kullanıcısı bulunamadı: {username}")
    try:
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ProviderError(f"GitHub yanıtı başarısız: {response.status_code}") from exc
    return parse_contributions(response.text, username, datetime.now())
