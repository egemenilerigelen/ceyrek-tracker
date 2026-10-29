"""JSON dosyalarını güvenli (atomik) okuma/yazma ve son verinin önbelleği."""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from ceyrek_tracker.domain.models import Snapshot

logger = logging.getLogger(__name__)


def read_json(path: Path) -> Any | None:
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        logger.warning("%s okunamadı, yok sayılıyor: %s", path.name, exc)
        return None


def write_json(path: Path, data: Any) -> None:
    """Önce geçici dosyaya yazıp sonra yer değiştirir; yarım dosya kalmaz."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class SnapshotCache:
    """Son başarılı veriyi saklar; uygulama açılır açılmaz ekranda bir şey olsun diye."""

    def __init__(self, path: Path) -> None:
        self.path = path

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
