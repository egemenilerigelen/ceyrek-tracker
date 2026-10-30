"""Global kısayol (Windows `RegisterHotKey`). Olay tabanlıdır, hiç polling yapmaz."""

from __future__ import annotations

import contextlib
import ctypes
import logging
import sys
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication, QObject, Signal

logger = logging.getLogger(__name__)

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
WM_HOTKEY = 0x0312

_MODIFIERS = {
    "alt": MOD_ALT,
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "meta": MOD_WIN,
    "super": MOD_WIN,
}
_NAMED_KEYS = {
    "space": 0x20,
    "enter": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "backspace": 0x08,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "insert": 0x2D,
    "delete": 0x2E,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
}


def parse_hotkey(spec: str) -> tuple[int, int] | None:
    """'win+alt+w' -> (değiştirici bayrakları, sanal tuş kodu); geçersizse None."""
    parts = [p.strip().lower() for p in spec.split("+") if p.strip()]
    if len(parts) < 2:
        return None  # Değiştiricisiz tek tuş global kısayol olamaz.
    *mods, key = parts
    flags = 0
    for mod in mods:
        if mod not in _MODIFIERS:
            return None
        flags |= _MODIFIERS[mod]
    if len(key) == 1 and key.isascii() and key.isalnum():
        vk = ord(key.upper())
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    elif key in _NAMED_KEYS:
        vk = _NAMED_KEYS[key]
    else:
        return None
    return flags, vk


class _Filter(QAbstractNativeEventFilter):
    def __init__(self, hotkey_id: int, callback) -> None:
        super().__init__()
        self._id = hotkey_id
        self._callback = callback

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == self._id:
                self._callback()
        return False, 0


class HotkeyManager(QObject):
    """Tek bir global kısayolu kaydeder; basılınca `triggered` yayınlar."""

    triggered = Signal()

    _ID = 0x7E57

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._filter: _Filter | None = None
        self._registered = False

    @property
    def registered(self) -> bool:
        return self._registered

    def register(self, spec: str) -> bool:
        """Kısayolu (yeniden) kaydeder. Geçersiz ya da başkası kullanıyorsa False."""
        self.unregister()
        if not spec or sys.platform != "win32":
            return False
        parsed = parse_hotkey(spec)
        if parsed is None:
            logger.warning("Geçersiz kısayol: %r", spec)
            return False
        flags, vk = parsed
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
        if not user32.RegisterHotKey(None, self._ID, flags | MOD_NOREPEAT, vk):
            logger.warning(
                "Kısayol kaydedilemedi (Windows hata kodu %d; 1409 = başka bir uygulama "
                "kullanıyor): %s",
                ctypes.get_last_error(),
                spec,
            )
            return False
        self._filter = _Filter(self._ID, self.triggered.emit)
        QCoreApplication.instance().installNativeEventFilter(self._filter)
        self._registered = True
        return True

    def unregister(self) -> None:
        if self._filter is not None:
            with contextlib.suppress(RuntimeError):
                QCoreApplication.instance().removeNativeEventFilter(self._filter)
            self._filter = None
        if self._registered:
            ctypes.windll.user32.UnregisterHotKey(None, self._ID)
            self._registered = False
