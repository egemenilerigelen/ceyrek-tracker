"""Çoklu monitörde hangi ekranın kullanılacağını seçen yardımcılar."""

from __future__ import annotations

from PySide6.QtGui import QCursor, QGuiApplication, QScreen


def screen_under_cursor() -> QScreen:
    return QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()


def resolve_screen(spec: str) -> QScreen:
    """'cursor' | 'primary' | ekran adı -> ekran. Bilinmeyen ad ana ekrana düşer."""
    if spec == "cursor":
        return screen_under_cursor()
    if spec != "primary":
        for screen in QGuiApplication.screens():
            if screen.name() == spec:
                return screen
    return QGuiApplication.primaryScreen()
