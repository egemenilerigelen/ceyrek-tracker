from datetime import date, datetime

import pytest

from ceyrek_tracker.cards.weather import api
from ceyrek_tracker.infra.http import ProviderError
from conftest import load_fixture

NOW = datetime(2026, 10, 30, 14, 0)


def test_parse_weather():
    w = api.parse_weather(load_fixture("open_meteo.json"), "İstanbul", NOW)
    assert (w.temperature, w.apparent, w.humidity, w.wind_kmh, w.code) == (15.2, 13.4, 80, 18.0, 2)
    assert w.precipitation_mm == 0.0
    assert [d.day for d in w.days] == [date(2026, 10, 30), date(2026, 10, 31), date(2026, 11, 1)]
    assert (w.days[1].temp_min, w.days[1].temp_max, w.days[1].code) == (13.0, 17.4, 61)


def test_weather_roundtrips_through_cache_dict():
    w = api.parse_weather(load_fixture("open_meteo.json"), "İstanbul", NOW)
    assert api.Weather.from_dict(w.to_dict()) == w


@pytest.mark.parametrize("payload", [None, {}, {"current": {}, "daily": {}}, {"current": 3}])
def test_parse_weather_rejects_malformed(payload):
    with pytest.raises(ProviderError):
        api.parse_weather(payload, "x", NOW)


def test_parse_place():
    payload = {"results": [{"name": "Ankara", "latitude": 39.9, "longitude": 32.8}]}
    place = api.parse_place(payload, "ankara")
    assert (place.query, place.name, place.latitude) == ("ankara", "Ankara", 39.9)
    with pytest.raises(ProviderError):
        api.parse_place({}, "yok")


def test_describe_known_and_unknown_codes():
    assert api.describe(2) == ("Parçalı bulutlu", api.KIND_PARTLY)
    assert api.describe(95)[1] == api.KIND_STORM
    assert api.describe(12345)[1] == api.KIND_CLOUDY
