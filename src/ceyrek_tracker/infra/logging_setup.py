"""Loglama: %APPDATA%\\CeyrekTakip\\logs\\app.log (dönen dosya) + varsa konsol."""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(log_dir: Path, level: int = logging.INFO) -> None:
    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter(_FORMAT)

    file_handler = RotatingFileHandler(
        log_dir / "app.log", maxBytes=512_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Pencereli exe'de (console=False) sys.stderr None olur.
    if sys.stderr is not None:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    # urllib3'ün her yeniden denemesini dosyaya yazmaya gerek yok.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
