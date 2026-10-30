"""Open-Meteo (ücretsiz, anahtarsız) ile hava durumu: konum arama, tahmin ve ayrıştırma.

Qt'ye bağlı değildir; kartın arayüzünden bağımsız test edilir.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import requests

from ceyrek_tracker.infra.http import ProviderError, get_json

logger = logging.getLogger(__name__)

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Görsel tür: arayüzdeki simge çizimi bu anahtarlara göre seçilir.
KIND_CLEAR = "clear"
KIND_PARTLY = "partly"
KIND_CLOUDY = "cloudy"
KIND_FOG = "fog"
KIND_RAIN = "rain"
KIND_SNOW = "snow"
KIND_STORM = "storm"

# WMO hava kodu -> (Türkçe açıklama, görsel tür)
_WMO: dict[int, tuple[str, str]] = {
    0: ("Açık", KIND_CLEAR),
    1: ("Çoğunlukla açık", KIND_CLEAR),
    2: ("Parçalı bulutlu", KIND_PARTLY),
    3: ("Kapalı", KIND_CLOUDY),
    45: ("Sisli", KIND_FOG),
    48: ("Kırağılı sis", KIND_FOG),
    51: ("Hafif çise", KIND_RAIN),
    53: ("Çise", KIND_RAIN),
    55: ("Yoğun çise", KIND_RAIN),
    56: ("Donan çise", KIND_RAIN),
    57: ("Yoğun donan çise", KIND_RAIN),
    61: ("Hafif yağmur", KIND_RAIN),
    63: ("Yağmurlu", KIND_RAIN),
    65: ("Şiddetli yağmur", KIND_RAIN),
    66: ("Donan yağmur", KIND_RAIN),
    67: ("Şiddetli donan yağmur", KIND_RAIN),
    71: ("Hafif kar", KIND_SNOW),
    73: ("Karlı", KIND_SNOW),
    75: ("Yoğun kar", KIND_SNOW),
    77: ("Kar taneleri", KIND_SNOW),
    80: ("Hafif sağanak", KIND_RAIN),
    81: ("Sağanak", KIND_RAIN),
    82: ("Şiddetli sağanak", KIND_RAIN),
    85: ("Kar sağanağı", KIND_SNOW),
    86: ("Yoğun kar sağanağı", KIND_SNOW),
    95: ("Gök gürültülü", KIND_STORM),
    96: ("Dolu ve fırtına", KIND_STORM),
    99: ("Şiddetli dolu ve fırtına", KIND_STORM),
}


def describe(code: int) -> tuple[str, str]:
    """WMO kodu -> (açıklama, görsel tür). Bilinmeyen kod nötr gösterilir."""
    return _WMO.get(code, ("Bilinmiyor", KIND_CLOUDY))


@dataclass(frozen=True)
class Place:
    query: str  # kullanıcının yazdığı ad; önbellek geçerliliği için
    name: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class DayForecast:
    day: date
    temp_min: float
    temp_max: float
    code: int


@dataclass(frozen=True)
class Weather:
    place: str
    temperature: float
    apparent: float
    humidity: int
    wind_kmh: float
    precipitation_mm: float
    code: int
    days: tuple[DayForecast, ...]
    fetched_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "place": self.place,
            "temperature": self.temperature,
            "apparent": self.apparent,
            "humidity": self.humidity,
            "wind_kmh": self.wind_kmh,
            "precipitation_mm": self.precipitation_mm,
            "code": self.code,
            "fetched_at": self.fetched_at.isoformat(),
            "days": [
                {"day": d.day.isoformat(), "min": d.temp_min, "max": d.temp_max, "code": d.code}
                for d in self.days
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Weather:
        return cls(
            place=data["place"],
            temperature=float(data["temperature"]),
            apparent=float(data["apparent"]),
            humidity=int(data["humidity"]),
            wind_kmh=float(data["wind_kmh"]),
            precipitation_mm=float(data["precipitation_mm"]),
            code=int(data["code"]),
            fetched_at=datetime.fromisoformat(data["fetched_at"]),
            days=tuple(
                DayForecast(
                    day=date.fromisoformat(d["day"]),
                    temp_min=float(d["min"]),
                    temp_max=float(d["max"]),
                    code=int(d["code"]),
                )
                for d in data["days"]
            ),
        )


def parse_place(payload: Any, query: str) -> Place:
    results = payload.get("results") if isinstance(payload, dict) else None
    if not results:
        raise ProviderError(f"'{query}' adlı konum bulunamadı")
    first = results[0]
    try:
        return Place(
            query=query,
            name=str(first["name"]),
            latitude=float(first["latitude"]),
            longitude=float(first["longitude"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ProviderError("Konum yanıtı beklenmeyen biçimde") from exc


def parse_weather(payload: Any, place_name: str, fetched_at: datetime) -> Weather:
    try:
        current = payload["current"]
        daily = payload["daily"]
        days = tuple(
            DayForecast(
                day=date.fromisoformat(day),
                temp_min=float(low),
                temp_max=float(high),
                code=int(code),
            )
            for day, low, high, code in zip(
                daily["time"],
                daily["temperature_2m_min"],
                daily["temperature_2m_max"],
                daily["weather_code"],
                strict=True,
            )
        )
        if not days:
            raise ProviderError("Hava tahmini boş geldi")
        return Weather(
            place=place_name,
            temperature=float(current["temperature_2m"]),
            apparent=float(current["apparent_temperature"]),
            humidity=round(float(current["relative_humidity_2m"])),
            wind_kmh=float(current["wind_speed_10m"]),
            # Yağış kutusu bugünün toplam yağışını gösterir.
            precipitation_mm=float(daily["precipitation_sum"][0] or 0.0),
            code=int(current["weather_code"]),
            days=days,
            fetched_at=fetched_at,
        )
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise ProviderError("Hava durumu yanıtı beklenmeyen biçimde") from exc


def find_place(session: requests.Session, query: str) -> Place:
    url = f"{GEOCODE_URL}?name={requests.utils.quote(query)}&count=1&language=tr&format=json"
    return parse_place(get_json(session, url), query)


def fetch_weather(session: requests.Session, place: Place) -> Weather:
    url = (
        f"{FORECAST_URL}?latitude={place.latitude}&longitude={place.longitude}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
        "weather_code,wind_speed_10m"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum"
        "&wind_speed_unit=kmh&timezone=auto&forecast_days=3"
    )
    return parse_weather(get_json(session, url), place.name, datetime.now())
