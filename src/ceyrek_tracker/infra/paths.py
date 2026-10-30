"""Dosya konumları (ortak olanlar).

Kartların kendi önbellek dosyası ilgili kartın paketinde belirlenir.
Kullanıcı verisi (ayarlar, önbellek, log) her zaman %APPDATA%\\CeyrekTakip altında
tutulur; uygulamanın hangi klasörden başlatıldığına bağlı değildir.
"""

from __future__ import annotations

import os
from pathlib import Path

from ceyrek_tracker import APP_NAME

# PyInstaller da modülleri paket yapısıyla açtığı için __file__ her iki durumda çalışır.
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
ICON_PATH = ASSETS_DIR / "icon.ico"


def data_dir() -> Path:
    override = os.environ.get("CEYREK_TAKIP_DATA_DIR")
    if override:
        base = Path(override)
    else:
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) / APP_NAME if appdata else Path.home() / f".{APP_NAME.lower()}"
    base.mkdir(parents=True, exist_ok=True)
    return base


def settings_file() -> Path:
    return data_dir() / "settings.json"


def log_dir() -> Path:
    path = data_dir() / "logs"
    path.mkdir(exist_ok=True)
    return path


def lock_file() -> Path:
    return data_dir() / "instance.lock"
