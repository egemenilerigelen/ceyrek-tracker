"""Windows'a özgü okuma: işlemci adı (kayıt defteri)."""

from __future__ import annotations

import logging
import platform

logger = logging.getLogger(__name__)

_CPU_KEY = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"


def cpu_name() -> str:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _CPU_KEY) as key:
            return str(winreg.QueryValueEx(key, "ProcessorNameString")[0]).strip()
    except (ImportError, OSError):
        logger.debug("İşlemci adı kayıt defterinden okunamadı", exc_info=True)
        return platform.processor() or "İşlemci"
