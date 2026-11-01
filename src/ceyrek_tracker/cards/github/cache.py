"""Son başarılı katkı tablosu; internet yokken eski tabloyu göstermek için diske yazılır."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

from ceyrek_tracker.cards.github.models import Contributions
from ceyrek_tracker.infra import paths
from ceyrek_tracker.infra.storage import read_json, write_json

logger = logging.getLogger(__name__)


def default_path() -> Path:
    return paths.data_dir() / "github.json"


class ContributionStore(Protocol):
    """Kartın ihtiyaç duyduğu önbellek arayüzü; testlerde değiştirilebilir."""

    def load(self) -> Contributions | None: ...

    def save(self, contributions: Contributions) -> None: ...


class ContributionCache:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_path()

    def load(self) -> Contributions | None:
        data = read_json(self.path)
        if not isinstance(data, dict):
            return None
        try:
            return Contributions.from_dict(data)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("GitHub önbelleği geçersiz: %s", exc)
            return None

    def save(self, contributions: Contributions) -> None:
        try:
            write_json(self.path, contributions.to_dict())
        except OSError as exc:
            logger.warning("GitHub önbelleği yazılamadı: %s", exc)
