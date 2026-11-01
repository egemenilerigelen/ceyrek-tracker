from datetime import date, datetime

import pytest
import requests

from ceyrek_tracker.cards.github import api
from ceyrek_tracker.cards.github.models import ContributionDay, Contributions
from ceyrek_tracker.infra.http import ProviderError
from conftest import FIXTURES

NOW = datetime(2026, 11, 2, 12, 0)


def _html() -> str:
    return (FIXTURES / "github_contributions.html").read_text(encoding="utf-8")


def test_parse_reads_counts_levels_and_sorts_by_date():
    data = api.parse_contributions(_html(), "ege", NOW)
    assert [(d.day, d.count, d.level) for d in data.days] == [
        (date(2026, 10, 19), 0, 0),
        (date(2026, 10, 20), 1, 1),
        (date(2026, 10, 21), 0, 0),
        (date(2026, 10, 26), 2, 2),
        (date(2026, 10, 27), 3, 4),
        (date(2026, 10, 28), 1, 1),
    ]
    assert data.total == 7
    assert data.username == "ege"


def test_parse_rejects_page_without_calendar():
    with pytest.raises(ProviderError):
        api.parse_contributions("<html><body>Not Found</body></html>", "ege", NOW)


def test_parse_rejects_cell_without_tooltip():
    html = _html().replace('for="contribution-day-component-0-1"', 'for="x"')
    with pytest.raises(ProviderError):
        api.parse_contributions(html, "ege", NOW)


def test_parse_rejects_unreadable_tooltip_and_bad_level():
    with pytest.raises(ProviderError):
        api.parse_contributions(
            _html().replace("2 contributions on October 26th.", "Bugün 2 katkı."), "ege", NOW
        )
    with pytest.raises(ProviderError):
        api.parse_contributions(_html().replace('data-level="4"', 'data-level="9"'), "ege", NOW)


class _Response:
    def __init__(self, status: int, text: str = "") -> None:
        self.status_code = status
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class _Session:
    def __init__(self, outcome) -> None:
        self.outcome = outcome
        self.calls: list[tuple[str, dict]] = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append((url, headers))
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def test_fetch_requests_profile_calendar_in_english():
    session = _Session(_Response(200, _html()))
    data = api.fetch_contributions(session, "egemenilerigelen")
    url, headers = session.calls[0]
    assert url == "https://github.com/users/egemenilerigelen/contributions"
    assert headers["Accept-Language"].startswith("en")
    assert data.total == 7


def test_fetch_reports_unknown_user_and_server_errors():
    with pytest.raises(ProviderError, match="bulunamadı"):
        api.fetch_contributions(_Session(_Response(404)), "ege")
    with pytest.raises(ProviderError, match="503"):
        api.fetch_contributions(_Session(_Response(503)), "ege")
    with pytest.raises(ProviderError, match="Bağlantı"):
        api.fetch_contributions(_Session(requests.ConnectionError()), "ege")


def test_fetch_rejects_username_that_is_not_a_github_login():
    session = _Session(_Response(200, _html()))
    for bad in ("", "a/b", "../x", "ege ilerigelen", "-ege"):
        with pytest.raises(ProviderError, match="Geçersiz"):
            api.fetch_contributions(session, bad)
    assert session.calls == []


def _contributions(*counts: int) -> Contributions:
    days = tuple(
        ContributionDay(date(2026, 10, 25 + i), c, min(c, 4)) for i, c in enumerate(counts)
    )
    return Contributions("ege", days, NOW)


def test_streak_counts_back_from_today_or_yesterday():
    data = _contributions(0, 2, 1, 3)  # 25..28 Ekim
    assert data.streak(date(2026, 10, 28)) == 3
    assert data.streak(date(2026, 10, 29)) == 3  # bugün veri yok: dünden geriye
    assert data.streak(date(2026, 10, 30)) == 0
    assert _contributions(1, 1, 0).streak(date(2026, 10, 27)) == 2  # bugün boş, dünden sayılır
    assert _contributions(1, 1, 0).streak(date(2026, 10, 28)) == 0  # dün de boş: seri bozuldu


def test_contributions_round_trip_through_dict():
    data = _contributions(0, 2, 5)
    assert Contributions.from_dict(data.to_dict()) == data
