"""Pencere arkasına Windows'un bulanık (acrylic) efektini uygular.

`SetWindowCompositionAttribute` belgelenmemiş ama Windows 10 1803'ten beri çalışan bir
API'dir. Başarısız olursa False döner; çağıran taraf düz yarı saydam boyamaya düşer.
"""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes

from PySide6.QtGui import QGuiApplication

logger = logging.getLogger(__name__)

_WCA_ACCENT_POLICY = 19
_ACCENT_DISABLED = 0
_ACCENT_ENABLE_ACRYLICBLURBEHIND = 4


class _AccentPolicy(ctypes.Structure):
    _fields_ = (
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    )


class _CompositionData(ctypes.Structure):
    _fields_ = (
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.c_void_p),
        ("SizeOfData", ctypes.c_size_t),
    )


def is_supported() -> bool:
    return sys.platform == "win32" and QGuiApplication.platformName() == "windows"


def _set_accent(hwnd: int, state: int, tint: int) -> bool:
    policy = _AccentPolicy(state, 0, tint, 0)
    data = _CompositionData(
        _WCA_ACCENT_POLICY,
        ctypes.cast(ctypes.pointer(policy), ctypes.c_void_p),
        ctypes.sizeof(policy),
    )
    func = ctypes.windll.user32.SetWindowCompositionAttribute
    func.argtypes = [wintypes.HWND, ctypes.POINTER(_CompositionData)]
    func.restype = wintypes.BOOL
    return bool(func(hwnd, ctypes.byref(data)))


def enable_glass(hwnd: int, tint: tuple[int, int, int], opacity: float) -> bool:
    """Pencerenin arkasını bulanıklaştırır; `tint` (r, g, b) rengi `opacity` kadar bindirilir."""
    if not is_supported():
        return False
    try:
        r, g, b = tint
        alpha = max(1, min(255, round(opacity * 255)))
        gradient = (alpha << 24) | (b << 16) | (g << 8) | r  # ABGR
        return _set_accent(hwnd, _ACCENT_ENABLE_ACRYLICBLURBEHIND, gradient)
    except (OSError, AttributeError, ValueError):
        logger.warning("Cam efekti uygulanamadı", exc_info=True)
        return False


def disable_glass(hwnd: int) -> None:
    if not is_supported():
        return
    try:
        _set_accent(hwnd, _ACCENT_DISABLED, 0)
    except (OSError, AttributeError):
        logger.debug("Cam efekti kapatılamadı", exc_info=True)


def _user32():
    user = ctypes.windll.user32
    user.SetWindowRgn.argtypes = [wintypes.HWND, wintypes.HRGN, wintypes.BOOL]
    user.SetWindowRgn.restype = ctypes.c_int
    return user


def round_window_region(hwnd: int, width: int, height: int, radius: int) -> None:
    """Pencereyi yuvarlak köşeli bir bölgeyle keser (boyutlar fiziksel piksel)."""
    if not is_supported():
        return
    try:
        gdi = ctypes.windll.gdi32
        gdi.CreateRoundRectRgn.argtypes = [ctypes.c_int] * 6
        gdi.CreateRoundRectRgn.restype = wintypes.HRGN
        gdi.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        region = gdi.CreateRoundRectRgn(0, 0, width + 1, height + 1, radius * 2, radius * 2)
        # Başarılı olursa bölgenin sahibi sistemdir; başarısızsa kendimiz silmeliyiz.
        if not _user32().SetWindowRgn(hwnd, region, True):
            gdi.DeleteObject(region)
    except (OSError, AttributeError, ctypes.ArgumentError):
        logger.debug("Pencere bölgesi ayarlanamadı", exc_info=True)


def clear_window_region(hwnd: int) -> None:
    if not is_supported():
        return
    try:
        _user32().SetWindowRgn(hwnd, None, True)
    except (OSError, AttributeError, ctypes.ArgumentError):
        logger.debug("Pencere bölgesi temizlenemedi", exc_info=True)
