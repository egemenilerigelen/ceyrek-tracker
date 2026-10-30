"""Tetikleyici arayüzü: paneli açtıran, ekran kenarındaki küçük bölge.

Yeni bir tetikleyici (ör. tam boy kenar şeridi) yazmak için `Trigger`'ı türetip
`core/trigger/__init__.py` içindeki `TRIGGER_KINDS` sözlüğüne eklemek yeterlidir.
Panel ve denetleyici yalnızca bu arayüzü bilir.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QScreen

from ceyrek_tracker.core.settings import Settings
from ceyrek_tracker.theme import Look


class Trigger(QObject):
    activated = Signal(QScreen)  # tıklandı
    hovered = Signal(QScreen, bool)  # fare üzerine geldi (True) / ayrıldı (False)

    def configure(self, settings: Settings, look: Look) -> None:
        """Ayar ya da tema değişince konum, boyut ve renkleri yeniler."""
        raise NotImplementedError

    def show_on(self, screen: QScreen) -> None:
        """Tetikleyiciyi verilen ekranın sağ kenarında gösterir."""
        raise NotImplementedError

    def hide(self) -> None:
        raise NotImplementedError

    def shutdown(self) -> None:
        self.hide()
