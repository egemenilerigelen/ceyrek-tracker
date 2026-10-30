"""Sistem tepsisi simgesi ve menüsü. Ne yapılacağına karar vermez, yalnızca sinyal yayınlar."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


class TrayIcon(QObject):
    toggle_requested = Signal()
    pin_toggled = Signal(bool)
    quit_requested = Signal()

    def __init__(
        self, icon: QIcon, tooltip: str, pinned: bool, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._title = tooltip
        menu = QMenu()
        menu.addAction("Paneli aç / kapat").triggered.connect(self.toggle_requested)
        self._pin_action: QAction = menu.addAction("Açık tut")
        self._pin_action.setCheckable(True)
        self._pin_action.setChecked(pinned)
        self._pin_action.triggered.connect(self.pin_toggled)
        menu.addSeparator()
        menu.addAction("Çıkış").triggered.connect(self.quit_requested)
        self._menu = menu  # QSystemTrayIcon menüyü sahiplenmez; referans tutulmalı
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip(tooltip)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)

    @staticmethod
    def is_available() -> bool:
        return QSystemTrayIcon.isSystemTrayAvailable()

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def set_pinned(self, pinned: bool) -> None:
        self._pin_action.setChecked(pinned)

    def warn(self, message: str) -> None:
        self._tray.showMessage(self._title, message, QSystemTrayIcon.MessageIcon.Warning, 6000)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.toggle_requested.emit()
