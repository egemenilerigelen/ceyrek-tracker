"""Uygulamanın giriş noktası ve bileşenleri birbirine bağlayan denetleyici."""

from __future__ import annotations

import contextlib
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QLockFile, QObject, QPoint, Slot
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from ceyrek_tracker import APP_DISPLAY_NAME, APP_NAME, __version__, paths
from ceyrek_tracker.domain.catalog import get_gold_type
from ceyrek_tracker.domain.formatting import format_price
from ceyrek_tracker.domain.models import FeedState, Snapshot
from ceyrek_tracker.logging_setup import setup_logging
from ceyrek_tracker.providers import PriceProvider, build_fetcher, create_providers
from ceyrek_tracker.services.price_service import PriceService
from ceyrek_tracker.settings import Settings, SettingsStore
from ceyrek_tracker.storage import SnapshotCache
from ceyrek_tracker.ui.main_window import WidgetWindow
from ceyrek_tracker.ui.menu import AppMenu

logger = logging.getLogger(__name__)

# Varsayılan konum: ekranın sağ üst köşesinden bu kadar içeride.
SCREEN_MARGIN = 24


def acquire_single_instance(lock_path: Path) -> QLockFile | None:
    """Aynı anda tek widget çalışsın diye kilit alır; başka kopya varsa None döner.

    Kilidi tutan işlem artık çalışmıyorsa (çökme, görev yöneticisinden sonlandırma) Qt
    kilidi kendisi bayat sayıp temizler; uygulama çöktükten sonra da açılır. Süre bazlı
    bayatlama kapatılır: widget günlerce açık kalır ve Qt'nin varsayılan 30 sn'si
    sonrasında canlı bir kopyanın kilidi çalınabilirdi. Windows'ta açık dosya tutamacı
    bunu zaten engeller; bu ayar Linux/macOS'ta da aynı davranışı garanti eder.
    """
    lock = QLockFile(str(lock_path))
    lock.setStaleLockTime(0)
    if lock.tryLock(100):
        return lock
    return None


class AppController(QObject):
    def __init__(
        self, app: QApplication, providers: dict[str, PriceProvider] | None = None
    ) -> None:
        super().__init__()
        self._app = app
        self._store = SettingsStore(paths.settings_file())
        self._settings = self._store.load()
        self._cache = SnapshotCache(paths.snapshot_file())
        self._providers = providers if providers is not None else create_providers()
        self._tray_hint_shown = False

        icon = QIcon(str(paths.ICON_PATH))
        self.window = WidgetWindow(icon)
        self.menu = AppMenu(self.window)
        self.service = PriceService(
            build_fetcher(self._providers, self._settings.provider),
            self._settings.refresh_seconds,
            initial=self._cache.load(),
            parent=self,
        )

        self.tray: QSystemTrayIcon | None = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = QSystemTrayIcon(icon, self)
            self.tray.setToolTip(APP_DISPLAY_NAME)
            self.tray.setContextMenu(self.menu.menu)
            self.tray.activated.connect(self._on_tray_activated)
            app.setQuitOnLastWindowClosed(False)
        else:
            # Tepsi yoksa pencere gizlenirse ulaşılamaz; kapatma gerçekten kapatsın.
            logger.warning("Sistem tepsisi yok; kapatma düğmesi uygulamadan çıkacak")
            self.window.allow_close()

        self._connect()
        self._apply_settings_to_window()
        self.menu.sync(self._settings)

    def _connect(self) -> None:
        s, w, m = self.service, self.window, self.menu
        s.snapshot_changed.connect(self._on_snapshot)
        s.state_changed.connect(self._on_state)

        w.featured_clicked.connect(self.set_featured)
        w.expand_toggled.connect(self.set_expanded)
        w.context_menu_requested.connect(self._show_context_menu)
        w.hidden_to_tray.connect(self._on_hidden_to_tray)

        m.toggle_window.connect(self.toggle_window)
        m.refresh_now.connect(s.refresh)
        m.featured_selected.connect(self.set_featured)
        m.visibility_toggled.connect(self.set_type_visible)
        m.provider_selected.connect(self.set_provider)
        m.interval_selected.connect(self.set_interval)
        m.always_on_top_toggled.connect(self.set_always_on_top)
        m.expanded_toggled.connect(self.set_expanded)
        m.quit_requested.connect(self.quit)

        self._app.aboutToQuit.connect(self._shutdown)

    # --- Yaşam döngüsü ------------------------------------------------------

    def start(self) -> None:
        self._place_window()
        self.window.show()
        if self.tray:
            self.tray.show()
        self.service.start()

    @Slot()
    def quit(self) -> None:
        self.window.allow_close()
        self._app.quit()

    @Slot()
    def _shutdown(self) -> None:
        self._update_settings(window_pos=(self.window.x(), self.window.y()))
        if self.tray:
            self.tray.hide()
        # Süren ağ isteği beklenmez: arka plan thread'i süreçle birlikte sonlanır.
        self.service.stop()

    # --- Ayar değişiklikleri --------------------------------------------------

    def _update_settings(self, **changes) -> Settings:
        self._settings = self._settings.with_changes(**changes)
        self._store.save(self._settings)
        self.menu.sync(self._settings)
        return self._settings

    @Slot(str)
    def set_featured(self, type_id: str) -> None:
        if get_gold_type(type_id) is None:
            return
        self._update_settings(featured=type_id)
        self.window.set_featured(type_id)
        self._update_tray_tooltip()

    @Slot(str, bool)
    def set_type_visible(self, type_id: str, visible: bool) -> None:
        current = list(self._settings.visible)
        if visible and type_id not in current:
            current.append(type_id)
        elif not visible and type_id in current:
            current.remove(type_id)
        settings = self._update_settings(visible=tuple(current))
        self.window.set_visible_types(settings.visible)

    @Slot(str)
    def set_provider(self, provider_id: str) -> None:
        if provider_id == self._settings.provider:
            return
        self._update_settings(provider=provider_id)
        self.service.set_fetcher(build_fetcher(self._providers, provider_id))

    @Slot(int)
    def set_interval(self, seconds: int) -> None:
        self._update_settings(refresh_seconds=seconds)
        self.service.set_interval(seconds)

    @Slot(bool)
    def set_always_on_top(self, on_top: bool) -> None:
        self._update_settings(always_on_top=on_top)
        self.window.set_always_on_top(on_top)

    @Slot(bool)
    def set_expanded(self, expanded: bool) -> None:
        self._update_settings(expanded=expanded)
        self.window.set_expanded(expanded)

    def _apply_settings_to_window(self) -> None:
        s = self._settings
        self.window.set_featured(s.featured)
        self.window.set_visible_types(s.visible)
        self.window.set_expanded(s.expanded)
        if s.always_on_top:
            self.window.set_always_on_top(True)

    # --- Pencere ve tepsi -----------------------------------------------------

    def _place_window(self) -> None:
        pos = self._settings.window_pos
        if pos is not None and QGuiApplication.screenAt(QPoint(*pos)) is not None:
            self.window.move(*pos)
            return
        # Kayıtlı konum yoksa ya da o ekran artık bağlı değilse sağ üst köşe.
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.window.adjustSize()
        x = screen.right() - self.window.width() - SCREEN_MARGIN
        self.window.move(x, screen.top() + SCREEN_MARGIN)

    @Slot()
    def toggle_window(self) -> None:
        if self.window.isVisible() and not self.window.isMinimized():
            self.window.hide()
        else:
            self.window.bring_to_front()

    @Slot(QSystemTrayIcon.ActivationReason)
    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.toggle_window()

    @Slot(QPoint)
    def _show_context_menu(self, global_pos: QPoint) -> None:
        self.menu.menu.popup(global_pos)

    @Slot()
    def _on_hidden_to_tray(self) -> None:
        self._update_settings(window_pos=(self.window.x(), self.window.y()))
        if self.tray and not self._tray_hint_shown:
            self._tray_hint_shown = True
            self.tray.showMessage(
                APP_DISPLAY_NAME,
                "Uygulama tepside çalışmaya devam ediyor. Çıkmak için sağ tıklayın.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )

    # --- Veri -------------------------------------------------------------------

    @Slot(object)
    def _on_snapshot(self, snapshot: Snapshot) -> None:
        self.window.show_snapshot(snapshot)
        self._update_tray_tooltip()
        self._cache.save(snapshot)

    @Slot(object)
    def _on_state(self, state: FeedState) -> None:
        self.window.set_state(state)
        self._update_tray_tooltip()

    def _update_tray_tooltip(self) -> None:
        if not self.tray:
            return
        snapshot = self.service.snapshot
        gold_type = get_gold_type(self._settings.featured)
        quote = snapshot.get(self._settings.featured) if snapshot else None
        if gold_type and quote:
            self.tray.setToolTip(
                f"{gold_type.name}\n"
                f"Alış {format_price(quote.buy, gold_type.currency)}  ·  "
                f"Satış {format_price(quote.sell, gold_type.currency)}"
            )
        else:
            self.tray.setToolTip(APP_DISPLAY_NAME)


def _set_windows_app_id() -> None:
    """Görev çubuğunda python.exe yerine uygulamanın kendi ikonu görünsün."""
    if sys.platform != "win32":
        return
    import ctypes

    with contextlib.suppress(AttributeError, OSError):
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("CeyrekTakip.Widget")


def main() -> int:
    setup_logging(paths.log_dir())
    logger.info("%s %s başlatılıyor", APP_NAME, __version__)
    _set_windows_app_id()

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
