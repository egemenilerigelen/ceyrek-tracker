"""Finans kartının son başarılı verisi: uygulama açılır açılmaz ekranda bir şey olsun diye."""

from __future__ import annotations

import logging
from pathlib import Path

from ceyrek_tracker.cards.finance.models import Snapshot
from ceyrek_tracker.infra import paths
from ceyrek_tracker.infra.storage import read_json, write_json

logger = logging.getLogger(__name__)


def default_path() -> Path:
    return paths.data_dir() / "last_snapshot.json"


class SnapshotCache:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_path()

    def load(self) -> Snapshot | None:
        data = read_json(self.path)
        if data is None:
            return None
        try:
            return Snapshot.from_dict(data)
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Önbellekteki veri geçersiz: %s", exc)
            return None

    def save(self, snapshot: Snapshot) -> None:
        try:
            write_json(self.path, snapshot.to_dict())
        except OSError as exc:
            logger.warning("Önbellek yazılamadı: %s", exc)
