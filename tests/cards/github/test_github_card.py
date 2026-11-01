from datetime import date, datetime, timedelta

from ceyrek_tracker.cards import CARDS, github
from ceyrek_tracker.cards.github import cache as github_cache
from ceyrek_tracker.cards.github.card import thousands
from ceyrek_tracker.cards.github.models import ContributionDay, Contributions
from ceyrek_tracker.core.card_base import CardContext
from ceyrek_tracker.theme import resolve_look

LOOK = resolve_look("dark", "normal", 1.0)


def _data(username="egemenilerigelen", fetched_at=None) -> Contributions:
    today = date.today()
    days = tuple(
        ContributionDay(today - timedelta(days=i), 2 if i < 3 else 0, 2 if i < 3 else 0)
        for i in range(29, -1, -1)
    )
    return Contributions(username, days, fetched_at or datetime.now())


class _Cache:
    def __init__(self, data=None) -> None:
        self.data, self.saved = data, []

    def load(self):
        return self.data

    def save(self, contributions):
        self.saved.append(contributions)


def _card(monkeypatch, fetch, cache=None, config=None):
    monkeypatch.setattr(github.GithubCard, "_fetch", fetch)
    return github.GithubCard(CardContext(LOOK, config or {}), cache or _Cache())


def _offline(self):
    raise OSError("çevrimdışı")


def test_card_is_registered():
    assert "github" in [spec.id for spec in CARDS]


def test_thousands_uses_dot_separator():
    assert thousands(290) == "290"
    assert thousands(1234) == "1.234"


def test_cached_data_renders_immediately_without_stale_label(qtbot, monkeypatch):
    card = _card(monkeypatch, _offline, _Cache(_data()))
    qtbot.addWidget(card)
    assert card._total.text() == "Son bir yılda 6 katkı"
    assert card._streak.text() == "Seri 3 gün"
    assert card.current_info == "@egemenilerigelen"
    qtbot.waitUntil(lambda: card._poller.running, timeout=3000)
    card.shutdown()


def test_failed_refresh_marks_cached_data_stale(qtbot, monkeypatch):
    stale = _data(fetched_at=datetime.now() - timedelta(hours=2))
    card = _card(monkeypatch, _offline, _Cache(stale))
    qtbot.addWidget(card)
    qtbot.waitUntil(lambda: "eski veri" in card.current_info, timeout=3000)
    assert card.current_error == ""
    card.shutdown()


def test_failure_without_cache_shows_error_then_success_clears_it(qtbot, monkeypatch):
    outcomes = iter([OSError("çevrimdışı"), _data()])

    def fetch(self):
        outcome = next(outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    card = _card(monkeypatch, fetch)
    qtbot.addWidget(card)
    qtbot.waitUntil(lambda: card.current_error.startswith("GitHub'a ulaşılamıyor"), timeout=3000)
    card._poller.refresh()
    qtbot.waitUntil(lambda: card.current_error == "", timeout=3000)
    assert card._total.text() == "Son bir yılda 6 katkı"
    card.shutdown()


def test_cache_for_another_user_is_ignored(qtbot, monkeypatch):
    card = _card(monkeypatch, _offline, _Cache(_data("baskasi")))
    qtbot.addWidget(card)
    assert card._total.text() == "Veri bekleniyor"
    card.shutdown()


def test_username_comes_from_config(qtbot, monkeypatch):
    card = _card(monkeypatch, _offline, config={"username": " octocat "})
    qtbot.addWidget(card)
    assert card.current_info == "@octocat"
    card.shutdown()


def test_invalid_refresh_setting_falls_back_to_default(qtbot, monkeypatch):
    card = _card(monkeypatch, _offline, config={"refresh_minutes": 1})
    qtbot.addWidget(card)
    assert card._interval == 30 * 60
    card.shutdown()


def test_cache_round_trip_and_corrupt_file(tmp_path):
    store = github_cache.ContributionCache(tmp_path / "github.json")
    assert store.load() is None
    data = _data()
    store.save(data)
    assert store.load() == data
    (tmp_path / "github.json").write_text('{"username": "x"}', encoding="utf-8")
    assert store.load() is None
