import json
import os
import subprocess
import sys
import time
from datetime import datetime

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QSystemTrayIcon

from ceyrek_tracker import paths
from ceyrek_tracker.app import AppController, acquire_single_instance
from ceyrek_tracker.domain.models import Quote, Snapshot
from ceyrek_tracker.storage import SnapshotCache


class StubProvider:
    def __init__(self, provider_id: str, name: str, buy: float = 100.0):
        self.id = provider_id
        self.name = name
        self.buy = buy
        self.calls = 0

    def fetch(self) -> Snapshot:
        self.calls += 1
        return Snapshot(
            source_id=self.id,
            source_name=self.name,
            quotes={
                "ceyrek": Quote("ceyrek", self.buy, self.buy + 10, 0.5),
                "gram": Quote("gram", 6000.0, 6100.0, -0.2),
            },
            fetched_at=datetime.now(),
        )


def saved_settings() -> dict:
    return json.loads(paths.settings_file().read_text(encoding="utf-8"))


@pytest.fixture
def providers():
    return {
        "truncgil": StubProvider("truncgil", "Truncgil"),
        "altinkaynak": StubProvider("altinkaynak", "Altinkaynak", buy=200.0),
    }


@pytest.fixture
def make_controller(qapp, qtbot, providers):
    created: list[AppController] = []
    quit_on_last_closed = qapp.quitOnLastWindowClosed()

    def make(custom_providers=None) -> AppController:
        controller = AppController(qapp, custom_providers or providers)
        # Her test kendi denetleyicisini kapatır; paylaşılan qapp'in kapanış sinyaline
        # bağlı kalmasınlar.
        qapp.aboutToQuit.disconnect(controller._shutdown)
        qtbot.addWidget(controller.window)
        created.append(controller)
        return controller

    yield make

    for controller in created:
        controller.service.stop()
        controller.window.allow_close()
        controller.window.close()
    qapp.setQuitOnLastWindowClosed(quit_on_last_closed)


@pytest.fixture
def with_tray(monkeypatch):
    """Offscreen ortamda da sistem tepsisi varmış gibi davran."""
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: True))
    messages: list[tuple] = []
    monkeypatch.setattr(
        QSystemTrayIcon, "showMessage", lambda self, *args, **kwargs: messages.append(args)
    )
    return messages


@pytest.fixture
def without_tray(monkeypatch):
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: False))


def wait_live(qtbot, controller: AppController) -> None:
    qtbot.waitUntil(lambda: controller.window.badge.text == "CANLI", timeout=3000)


# --- Açılış ve veri akışı -----------------------------------------------------


def test_cached_snapshot_is_shown_immediately_as_stale(make_controller):
    old = Snapshot(
        "truncgil", "Truncgil", {"ceyrek": Quote("ceyrek", 555.0, 565.0)}, datetime.now()
    )
    SnapshotCache(paths.snapshot_file()).save(old)

    controller = make_controller()
    controller.start()

    # Henüz ağdan yanıt gelmeden son bilinen veri ekranda, rozet dürüstçe "gecikmeli".
    assert controller.window.featured_panel.buy_label.text() == "555,00"
    assert controller.window.badge.text == "GECİKMELİ"


def test_fetch_updates_window_and_saves_cache(qtbot, make_controller):
    controller = make_controller()
    controller.start()
    wait_live(qtbot, controller)

    assert controller.window.featured_panel.buy_label.text() == "100,00"
    assert "Truncgil" in controller.window.status_label.text()
    cached = SnapshotCache(paths.snapshot_file()).load()
    assert cached is not None
    assert cached.source_id == "truncgil"


def test_provider_switch_fetches_from_new_source_and_persists(qtbot, make_controller, providers):
    controller = make_controller()
    controller.start()
    wait_live(qtbot, controller)

    controller.set_provider("altinkaynak")
    qtbot.waitUntil(
        lambda: controller.window.featured_panel.buy_label.text() == "200,00", timeout=3000
    )
    assert saved_settings()["provider"] == "altinkaynak"

    # Aynı kaynak yeniden seçilirse gereksiz istek atılmaz.
    calls = providers["altinkaynak"].calls
    controller.set_provider("altinkaynak")
    qtbot.wait(150)
    assert providers["altinkaynak"].calls == calls


# --- Ayarlar ----------------------------------------------------------------


def test_featured_is_persisted_and_applied(make_controller):
    controller = make_controller()
    controller.set_featured("gram")
    assert saved_settings()["featured"] == "gram"
    assert controller.window.featured_panel.name_label.text() == "GRAM ALTIN"
    assert controller.menu._featured_actions["gram"].isChecked()


def test_unknown_featured_type_is_ignored(make_controller):
    controller = make_controller()
    controller.set_featured("platin")
    assert not paths.settings_file().exists()
    assert controller.window.featured_panel.name_label.text() == "ÇEYREK ALTIN"


def test_visibility_toggle(make_controller):
    controller = make_controller()
    controller.set_type_visible("ons", False)
    assert "ons" not in saved_settings()["visible"]
    assert controller.window.price_list.rows["ons"].isHidden()

    controller.set_type_visible("ons", True)
    assert "ons" in saved_settings()["visible"]
    assert not controller.window.price_list.rows["ons"].isHidden()


def test_interval_expanded_and_always_on_top(make_controller):
    controller = make_controller()
    controller.set_interval(300)
    controller.set_expanded(True)
    controller.set_always_on_top(True)

    saved = saved_settings()
    assert saved["refresh_seconds"] == 300
    assert saved["expanded"] is True
    assert saved["always_on_top"] is True
    assert not controller.window.price_list.isHidden()
    assert controller.window.windowFlags() & Qt.WindowType.WindowStaysOnTopHint


def test_settings_are_restored_on_next_launch(make_controller):
    first = make_controller()
    first.set_featured("yarim")
    first.set_expanded(True)
    first.set_type_visible("ons", False)
    first.set_provider("altinkaynak")
    first.set_interval(120)

    second = make_controller()
    assert second.window.featured_panel.name_label.text() == "YARIM ALTIN"
    assert not second.window.price_list.isHidden()
    assert second.window.price_list.rows["ons"].isHidden()
    assert second.menu._provider_actions["altinkaynak"].isChecked()
    assert second.menu._interval_actions[120].isChecked()
    assert second.menu._featured_actions["yarim"].isChecked()


def test_menu_actions_drive_the_controller(make_controller):
    controller = make_controller()
    menu = controller.menu

    menu._featured_actions["gram"].trigger()
    menu._provider_actions["altinkaynak"].trigger()
    menu._interval_actions[300].trigger()
    menu._visible_actions["ons"].setChecked(False)
    menu._expanded_action.trigger()
    menu._on_top_action.trigger()

    saved = saved_settings()
    assert saved["featured"] == "gram"
    assert saved["provider"] == "altinkaynak"
    assert saved["refresh_seconds"] == 300
    assert "ons" not in saved["visible"]
    assert saved["expanded"] is True
    assert saved["always_on_top"] is True


# --- Pencere konumu -----------------------------------------------------------


def test_window_position_is_saved_on_shutdown_and_restored(make_controller):
    first = make_controller()
    first.start()
    first.window.move(40, 60)
    first._shutdown()
    assert saved_settings()["window_pos"] == [40, 60]

    second = make_controller()
    second.start()
    assert (second.window.x(), second.window.y()) == (40, 60)


def test_saved_position_on_missing_screen_falls_back_to_visible_default(make_controller):
    paths.settings_file().write_text(json.dumps({"window_pos": [90000, 90000]}), encoding="utf-8")
    controller = make_controller()
    controller.start()

    screen = QGuiApplication.primaryScreen().availableGeometry()
    assert screen.contains(QPoint(controller.window.x(), controller.window.y()))
    assert controller.window.geometry().right() <= screen.right()


# --- Tepsi ve kapatma ---------------------------------------------------------


def test_close_button_hides_to_tray_and_hints_only_once(make_controller, with_tray):
    controller = make_controller()
    controller.start()
    assert controller.tray is not None

    controller.window.close()
    assert not controller.window.isVisible()
    assert len(with_tray) == 1
    assert saved_settings()["window_pos"] is not None

    controller.window.show()
    controller.window.close()
    assert len(with_tray) == 1


def test_tray_click_toggles_window(make_controller, with_tray):
    controller = make_controller()
    controller.start()
    trigger = QSystemTrayIcon.ActivationReason.Trigger

    controller.tray.activated.emit(trigger)
    assert not controller.window.isVisible()
    controller.tray.activated.emit(trigger)
    assert controller.window.isVisible()

    # Sağ tık (Context) pencereyi etkilememeli; menüyü sistem açar.
    controller.tray.activated.emit(QSystemTrayIcon.ActivationReason.Context)
    assert controller.window.isVisible()


def test_tray_tooltip_follows_featured_price(qtbot, make_controller, with_tray):
    controller = make_controller()
    controller.start()
    wait_live(qtbot, controller)

    tip = controller.tray.toolTip()
    assert "Çeyrek Altın" in tip
    assert "100,00" in tip and "110,00" in tip

    controller.set_featured("gram")
    assert "Gram Altın" in controller.tray.toolTip()
    assert "6.000,00" in controller.tray.toolTip()


def test_quit_lets_window_close_for_real(make_controller, with_tray, qapp, monkeypatch):
    quit_calls: list[int] = []
    monkeypatch.setattr(qapp, "quit", lambda: quit_calls.append(1))
    controller = make_controller()
    controller.start()

    controller.quit()
    assert quit_calls == [1]
    assert controller.window.close()  # closeEvent kabul etti, tepsiye saklanmadı


def test_without_tray_close_button_really_closes(make_controller, without_tray):
    controller = make_controller()
    controller.start()
    assert controller.tray is None

    assert controller.window.close()
    assert not controller.window.isVisible()


# --- Fare etkileşimi ----------------------------------------------------------


def test_clicking_a_list_row_features_that_type(qtbot, make_controller):
    controller = make_controller()
    controller.set_expanded(True)
    controller.start()
    qtbot.waitExposed(controller.window)

    row = controller.window.price_list.rows["gram"]
    qtbot.mouseClick(row.name_label, Qt.MouseButton.LeftButton)

    assert saved_settings()["featured"] == "gram"
    assert controller.window.featured_panel.name_label.text() == "GRAM ALTIN"


# --- Tek kopya kilidi -----------------------------------------------------------

_HOLDER = """
import sys, time
from pathlib import Path
from ceyrek_tracker.app import acquire_single_instance
lock = acquire_single_instance(Path(sys.argv[1]))
print("locked" if lock else "failed", flush=True)
time.sleep(120)
"""


def test_second_instance_cannot_take_the_lock(tmp_path):
    path = tmp_path / "app.lock"
    first = acquire_single_instance(path)
    assert first is not None
    assert acquire_single_instance(path) is None

    first.unlock()
    again = acquire_single_instance(path)
    assert again is not None
    again.unlock()


def test_lock_survives_age_but_not_a_dead_owner(tmp_path):
    path = tmp_path / "app.lock"
    holder = subprocess.Popen(
        [sys.executable, "-c", _HOLDER, str(path)], stdout=subprocess.PIPE, text=True
    )
    try:
        assert holder.stdout.readline().strip() == "locked"
        assert acquire_single_instance(path) is None

        # Widget günlerce açık kalır: kilit dosyası ne kadar eskirse eskisin, sahibi
        # yaşadığı sürece ikinci kopya kilidi alamamalı. (Windows'ta açık tutamaç bunu
        # zaten sağlar; asıl koruma setStaleLockTime(0) ile Linux/macOS'ta devreye girer.)
        old = time.time() - 3600
        os.utime(path, (old, old))
        assert acquire_single_instance(path) is None
    finally:
        holder.kill()
        holder.wait()

    # Sahibi öldü (çökme / görev yöneticisinden sonlandırma): uygulama yine açılabilmeli.
    reclaimed = acquire_single_instance(path)
    assert reclaimed is not None
    reclaimed.unlock()
