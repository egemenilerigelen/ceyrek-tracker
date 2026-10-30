"""Uygulamanın giriş noktası ve bileşenleri birbirine bağlayan denetleyici.

Burası bileşenlerin tek bağlandığı yerdir (composition root): çekirdek (`core`) kartları,
kartlar da birbirini bilmez; kimin kime bağlanacağı yalnızca burada belirlenir.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Sequence

from PySide6.QtCore import QObject, QTimer, Slot
from PySide6.QtGui import QIcon, QScreen
from PySide6.QtWidgets import QApplication, QMessageBox

from ceyrek_tracker import APP_DISPLAY_NAME, APP_NAME, __version__
from ceyrek_tracker.cards import CARDS
from ceyrek_tracker.core.auto_close import PanelAutoClose, Pointer
from ceyrek_tracker.core.card_base import CardSpec
from ceyrek_tracker.core.card_manager import CardManager
from ceyrek_tracker.core.panel_window import PanelWindow
from ceyrek_tracker.core.platform.appid import set_app_user_model_id
from ceyrek_tracker.core.platform.hotkey import HotkeyManager
from ceyrek_tracker.core.platform.mouse import SystemPointer
from ceyrek_tracker.core.platform.single_instance import acquire_single_instance
from ceyrek_tracker.core.screens import resolve_screen
from ceyrek_tracker.core.settings import SettingsStore, look_from_settings
from ceyrek_tracker.core.tray import TrayIcon
from ceyrek_tracker.core.trigger import create_trigger
from ceyrek_tracker.infra import paths
from ceyrek_tracker.infra.logging_setup import setup_logging

logger = logging.getLogger(__name__)

APP_USER_MODEL_ID = "CeyrekTakip.Panel"


class AppController(QObject):
    def __init__(
        self,
        app: QApplication,
        specs: Sequence[CardSpec] | None = None,
        hotkeys: HotkeyManager | None = None,
        store: SettingsStore | None = None,
        pointer: Pointer | None = None,
    ) -> None:
        super().__init__()
        self._app = app
        self._store = store or SettingsStore(paths.settings_file())
        self.settings = self._store.load()
        self.look = look_from_settings(self.settings)

        icon = QIcon(str(paths.ICON_PATH))
        self.manager = CardManager(
            specs if specs is not None else CARDS,
            self.settings.cards,
            self.look,
            animate=self.settings.animations,
            parent=self,
        )
        self.settings = self.settings.with_changes(cards=self.manager.card_settings())

        self.panel = PanelWindow(self.look, self.settings)
        self.panel.setWindowIcon(icon)
        self.panel.set_pinned(self.settings.pinned)
        for host in self.manager.hosts:
            self.panel.add_host(host)

        self.trigger = create_trigger(self.settings.trigger_kind)
        self.trigger.configure(self.settings, self.look)
        self.hotkeys = hotkeys or HotkeyManager(self)
        self.auto_close = PanelAutoClose(
            zone=self.panel.target_rect,
            policy=lambda: self.settings,
            pointer=pointer or SystemPointer(),
            parent=self,
        )

        self._hover_screen: QScreen | None = None
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._open_hovered)

        self.tray: TrayIcon | None = None
        if TrayIcon.is_available():
            self.tray = TrayIcon(icon, APP_DISPLAY_NAME, self.settings.pinned, self)
            app.setQuitOnLastWindowClosed(False)

        self._connect()

    def _connect(self) -> None:
        self.trigger.hovered.connect(self._on_trigger_hovered)
        self.trigger.activated.connect(self.open_panel)
        self.hotkeys.triggered.connect(lambda: self.toggle_panel(self.settings.hotkey_screen))
        self.panel.pin_clicked.connect(lambda: self.set_pinned(not self.settings.pinned))
        self.panel.hidden.connect(self._on_panel_hidden)
        self.auto_close.close_requested.connect(self.close_panel)
        self.manager.collapsed_changed.connect(self._on_collapsed)
        self.manager.config_changed.connect(self._on_card_config)
        self._app.aboutToQuit.connect(self._shutdown)
        if self.tray is not None:
            self.tray.toggle_requested.connect(lambda: self.toggle_panel("cursor"))
            self.tray.pin_toggled.connect(self.set_pinned)
            self.tray.quit_requested.connect(self.quit)

    # --- Yaşam döngüsü ------------------------------------------------------

    def start(self) -> None:
        screen = resolve_screen(self.settings.trigger_screen)
        self.trigger.show_on(screen)
        if self.settings.hotkey and not self.hotkeys.register(self.settings.hotkey):
            self._notify(
                f"'{self.settings.hotkey}' kısayolu kaydedilemedi; başka bir uygulama "
                "kullanıyor olabilir. Paneli tutamaçtan ya da tepsi ikonundan açabilirsin."
            )
        if self.tray:
            self.tray.show()
        if self.settings.pinned:
            self.open_panel(screen)

    @Slot()
    def quit(self) -> None:
        self._app.quit()

    @Slot()
    def _shutdown(self) -> None:
        self.auto_close.stop()
        self.manager.shutdown()
        self.hotkeys.unregister()
        self.trigger.shutdown()
        if self.tray:
            self.tray.hide()
        self._store.save(self.settings)

    def _notify(self, message: str) -> None:
        logger.warning(message)
        if self.tray:
            self.tray.warn(message)

    # --- Panel açma / kapama ------------------------------------------------

    @Slot(QScreen)
    def open_panel(self, screen: QScreen) -> None:
        if self.panel.is_open:
            return
        self._hover_timer.stop()
        self.trigger.hide()
        self.panel.open_on(screen)
        self.manager.show_all()
        self.auto_close.start()

    def close_panel(self, force: bool = False) -> None:
        """Sabitliyken yalnızca `force` ile (kısayol, tepsi, iğne) kapanır."""
        if not self.panel.is_open or (self.settings.pinned and not force):
            return
        self._hover_timer.stop()
        self.auto_close.stop()
        self.panel.close_panel()
        self.manager.hide_all()

    def toggle_panel(self, screen_spec: str) -> None:
        if self.panel.is_open:
            self.close_panel(force=True)
        else:
            self.open_panel(resolve_screen(screen_spec))

    @Slot()
    def _on_panel_hidden(self) -> None:
        if not self.panel.is_open:
            self.trigger.show_on(resolve_screen(self.settings.trigger_screen))

    @Slot(QScreen, bool)
    def _on_trigger_hovered(self, screen: QScreen, entered: bool) -> None:
        if self.settings.open_mode != "hover":
            return
        if entered:
            self._hover_screen = screen
            self._hover_timer.start(self.settings.hover_delay_ms)
        else:
            self._hover_timer.stop()

    @Slot()
    def _open_hovered(self) -> None:
        if self._hover_screen is not None:
            self.open_panel(self._hover_screen)

    # --- Ayar değişiklikleri --------------------------------------------------

    def _update_settings(self, **changes) -> None:
        self.settings = self.settings.with_changes(**changes)
        self._store.save(self.settings)

    @Slot(bool)
    def set_pinned(self, pinned: bool) -> None:
        self._update_settings(pinned=pinned)
        self.panel.set_pinned(pinned)
        if self.tray is not None:
            self.tray.set_pinned(pinned)
        if not pinned:
            self.auto_close.reset()  # sabitlik kalkınca fare takibi sıfırdan başlasın

    @Slot(str, bool)
    def _on_collapsed(self, card_id: str, collapsed: bool) -> None:
        self.manager.set_collapsed(card_id, collapsed)
        self._update_settings(cards=self.manager.card_settings())

    @Slot(str, object)
    def _on_card_config(self, card_id: str, config: dict) -> None:
        self.manager.set_config(card_id, config)
        self._update_settings(cards=self.manager.card_settings())


def main() -> int:
    setup_logging(paths.log_dir())
    logger.info("%s %s başlatılıyor", APP_NAME, __version__)
    set_app_user_model_id(APP_USER_MODEL_ID)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_DISPLAY_NAME)
    app.setApplicationVersion(__version__)

    lock = acquire_single_instance(paths.lock_file())
    if lock is None:
        QMessageBox.information(
            None, APP_DISPLAY_NAME, "Uygulama zaten çalışıyor (sistem tepsisine bakın)."
        )
        return 0

    controller = AppController(app)
    controller.start()
    exit_code = app.exec()
    lock.unlock()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
