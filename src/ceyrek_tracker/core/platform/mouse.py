"""Fare durumu: imleç konumu ve (uygulama dışı pencereler dahil) düğme basılı mı."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

from PySide6.QtCore import QPoint
from PySide6.QtGui import QCursor

VK_LBUTTON, VK_RBUTTON = 0x01, 0x02


class SystemPointer:
    """`core.auto_close.Pointer` arayüzünün gerçek (sistem) uygulaması."""

    def position(self) -> QPoint:
        return QCursor.pos()

    def button_down(self) -> bool:
        if sys.platform != "win32":
            return False
        func = ctypes.windll.user32.GetAsyncKeyState
        func.argtypes = [ctypes.c_int]
        func.restype = wintypes.SHORT
        return bool(func(VK_LBUTTON) & 0x8000 or func(VK_RBUTTON) & 0x8000)
