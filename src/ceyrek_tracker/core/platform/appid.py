"""Windows görev çubuğu kimliği."""

from __future__ import annotations

import contextlib
import sys


def set_app_user_model_id(app_id: str) -> None:
    """Görev çubuğunda python.exe yerine uygulamanın kendi kimliği görünsün."""
    if sys.platform != "win32":
        return
    import ctypes

    with contextlib.suppress(AttributeError, OSError):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
