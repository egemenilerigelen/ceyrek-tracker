"""Hava durumunun son başarılı yanıtı; internet yokken eski veriyi göstermek için diske yazılır."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from ceyrek_tracker.cards.weather import api
from ceyrek_tracker.infra import paths
from ceyrek_tracker.infra.storage import read_json, write_json

logger = logging.getLogger(__name__)


def default_path() -> Path:
    return paths.data_dir() / "weather.json"


class WeatherStore(Protocol):
    """Kartın ihtiyaç duyduğu önbellek arayüzü; testlerde ve başka depolarda değiştirilebilir."""

    def load(self) -> tuple[api.Place | None, api.Weather | None]: ...

    def save(self, place: api.Place, weather: api.Weather) -> None: ...


class WeatherCache:
    """Son başarılı yanıt; internet yokken eski veriyi göstermek için diske yazılır."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_path()

    def load(self) -> tuple[api.Place | None, api.Weather | None]:
        data = read_json(self.path)
        if not isinstance(data, dict):
            return None, None
        place = weather = None
        try:
            if p := data.get("place"):
                place = api.Place(
                    p["query"], p["name"], float(p["latitude"]), float(p["longitude"])
                )
            if w := data.get("weather"):
                weather = api.Weather.from_dict(w)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Hava durumu önbelleği geçersiz: %s", exc)
        return place, weather

    def save(self, place: api.Place, weather: api.Weather) -> None:
        try:
            write_json(
                self.path,
                {
                    "place": {
                        "query": place.query,
                        "name": place.name,
                        "latitude": place.latitude,
                        "longitude": place.longitude,
                    },
                    "weather": weather.to_dict(),
                },
            )
        except OSError as exc:
            logger.warning("Hava durumu önbelleği yazılamadı: %s", exc)
