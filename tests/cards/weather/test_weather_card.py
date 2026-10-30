from datetime import date, datetime

from PySide6.QtCore import Qt

from ceyrek_tracker.cards import weather
from ceyrek_tracker.cards.weather import api
from ceyrek_tracker.cards.weather.card import day_label
from ceyrek_tracker.cards.weather.places import PLACES
from ceyrek_tracker.core.card_base import CardContext
from ceyrek_tracker.core.card_host import CardHost
from ceyrek_tracker.theme import resolve_look
from conftest import load_fixture

NOW = datetime(2026, 10, 30, 14, 0)


def test_day_label():
    today = date(2026, 10, 30)
    assert day_label(today, today) == "Bugün"
    assert day_label(date(2026, 10, 31), today) == "Yarın"
    assert day_label(date(2026, 11, 1), today) == "Pazar"


class _NoCache:
    def load(self):
        return None, None

    def save(self, place, weather):
        pass


def _weather_card(monkeypatch, config):
    monkeypatch.setattr(weather.WeatherCard, "_fetch", lambda self: (_ for _ in ()).throw(OSError))
    return weather.WeatherCard(CardContext(resolve_look("dark", "normal", 1.0), config), _NoCache())


def test_weather_defaults_to_urla(qtbot, monkeypatch):
    card = _weather_card(monkeypatch, {})
    qtbot.addWidget(card)
    assert card._city == "Urla"
    assert [a.isChecked() for a in card._city_actions.values()] == [False, True, False]
    card.shutdown()


def test_weather_city_selection_is_saved_and_resets_view(qtbot, monkeypatch):
    card = _weather_card(monkeypatch, {})
    qtbot.addWidget(card)
    card._poller.stop()
    with qtbot.waitSignal(card.config_changed) as blocker:
        card._city_actions["İzmir"].trigger()
    assert blocker.args == [{"city": "İzmir"}]
    assert card._city == "İzmir"
    assert card._temp.text() == "--°"
    assert card.current_info == "İzmir"
    assert [a.isChecked() for a in card._city_actions.values()] == [False, False, True]
    card.shutdown()


def test_clicking_city_name_opens_menu_without_collapsing(qtbot, monkeypatch):

    card = _weather_card(monkeypatch, {})
    card._poller.stop()
    host = CardHost(weather.SPEC, card, resolve_look("dark", "normal", 1.0), animate=False)
    qtbot.addWidget(host)
    host.show()
    assert host._info.text() == "Urla"  # veri gelmeden de konum adı görünür
    qtbot.mouseClick(host._info, Qt.MouseButton.LeftButton)
    assert card.info_menu.isVisible()
    assert not host.collapsed
    card.info_menu.close()
    card.shutdown()


def _cached_card(monkeypatch, fetch):

    cached = api.parse_weather(load_fixture("open_meteo.json"), "Urla", NOW)

    class _Cache(_NoCache):
        def load(self):
            return PLACES["Urla"], cached

    monkeypatch.setattr(weather.WeatherCard, "_fetch", fetch)
    return weather.WeatherCard(CardContext(resolve_look("dark", "normal", 1.0), {}), _Cache())


def test_cached_data_is_not_labelled_stale_on_startup(qtbot, monkeypatch):
    card = _cached_card(monkeypatch, lambda self: (_ for _ in ()).throw(OSError("çevrimdışı")))
    qtbot.addWidget(card)
    assert card._temp.text() == "15°"  # önbellek hemen gösterilir
    assert card.current_info == "Urla"  # henüz hata yok, "eski veri" yazısı yok
    qtbot.waitUntil(lambda: "eski veri" in card.current_info, timeout=3000)  # çevrimdışı kalınca
    card.shutdown()


def test_successful_refresh_clears_stale_label(qtbot, monkeypatch):

    results = iter([OSError("çevrimdışı"), None])

    def fetch(self):
        outcome = next(results)
        if isinstance(outcome, Exception):
            raise outcome
        return PLACES["Urla"], api.parse_weather(load_fixture("open_meteo.json"), "Urla", NOW)

    card = _cached_card(monkeypatch, fetch)
    qtbot.addWidget(card)
    qtbot.waitUntil(lambda: "eski veri" in card.current_info, timeout=3000)
    card._poller.refresh()
    qtbot.waitUntil(lambda: card.current_info == "Urla", timeout=3000)
    card.shutdown()
