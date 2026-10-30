import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QGuiApplication

from ceyrek_tracker.app import AppController
from ceyrek_tracker.core.card_base import Card, CardSpec
from ceyrek_tracker.core.platform.hotkey import HotkeyManager
from ceyrek_tracker.core.settings import Settings, SettingsStore


class _FakeHotkeys(HotkeyManager):
    """Testler gerçek global kısayol kaydetmesin."""

    def __init__(self):
        super().__init__()
        self.spec = None

    def register(self, spec):
        self.spec = spec
        return True

    def unregister(self):
        self.spec = None


class _FakePointer:
    """Testler gerçek fareye bağlı kalmasın."""

    def __init__(self, down=False, pos=None):
        self.down = down
        self.pos = pos if pos is not None else QPoint(0, 0)

    def position(self):
        return self.pos

    def button_down(self):
        return self.down


class _Plain(Card):
    pass


SPEC = CardSpec("plain", "Düz", "", _Plain)


@pytest.fixture
def make_controller(qapp, tmp_path):
    controllers = []

    def make(pointer=None, **settings):
        store = SettingsStore(tmp_path / "settings.json")
        store.save(Settings(animations=False, **settings))
        controller = AppController(
            qapp,
            specs=[SPEC],
            hotkeys=_FakeHotkeys(),
            store=store,
            pointer=pointer or _FakePointer(),
        )
        controllers.append(controller)
        return controller

    yield make
    for controller in controllers:
        controller.hotkeys.unregister()
        controller.trigger.shutdown()
        controller.manager.shutdown()
        controller.panel.close_panel()
        controller.auto_close.stop()


@pytest.fixture
def screen(qapp):
    return QGuiApplication.primaryScreen()


def test_open_and_close_runs_card_lifecycle(make_controller, screen):
    c = make_controller()
    c.open_panel(screen)
    assert c.panel.is_open
    assert c.manager.hosts[0].card is not None
    c.close_panel()
    assert not c.panel.is_open


def test_panel_never_leaves_the_work_area(make_controller, screen):
    c = make_controller()
    c.open_panel(screen)
    work = screen.availableGeometry()
    rect = c.panel.target_rect()
    assert work.contains(rect)
    assert rect.right() == work.right()
    assert rect.height() == work.height()


def test_pinned_panel_ignores_soft_close_but_not_forced(make_controller, screen):
    c = make_controller(pinned=True)
    c.start()
    assert c.panel.is_open  # sabit durum açılışta hatırlanır
    c.close_panel()
    assert c.panel.is_open
    c.toggle_panel("primary")
    assert not c.panel.is_open


def test_pin_toggle_is_persisted(make_controller, tmp_path):
    c = make_controller()
    c.set_pinned(True)
    assert SettingsStore(tmp_path / "settings.json").load().pinned


def test_hover_opens_after_delay_only_in_hover_mode(make_controller, screen, qtbot):
    c = make_controller(hover_delay_ms=20)
    c._on_trigger_hovered(screen, True)
    qtbot.waitUntil(lambda: c.panel.is_open, timeout=2000)
    c.close_panel()

    clicky = make_controller(open_mode="click", hover_delay_ms=20)
    clicky._on_trigger_hovered(screen, True)
    qtbot.wait(150)
    assert not clicky.panel.is_open
    clicky.open_panel(screen)  # tıklama her modda açar
    assert clicky.panel.is_open


def test_hover_leave_before_delay_cancels_open(make_controller, screen, qtbot):
    c = make_controller(hover_delay_ms=200)
    c._on_trigger_hovered(screen, True)
    c._on_trigger_hovered(screen, False)
    qtbot.wait(300)
    assert not c.panel.is_open


def test_outside_click_closes_panel_through_auto_close(make_controller, screen):
    pointer = _FakePointer(down=False, pos=QPoint(0, 0))
    c = make_controller(pointer=pointer)
    c.open_panel(screen)
    c.auto_close.tick()  # düğme bırakılmış: tıklamalar artık sayılır
    pointer.down = True
    c.auto_close.tick()  # panel dışında yeni tıklama
    assert not c.panel.is_open


def test_pinned_panel_ignores_outside_click(make_controller, screen):
    pointer = _FakePointer(down=True, pos=QPoint(0, 0))
    c = make_controller(pinned=True, pointer=pointer)
    c.open_panel(screen)
    c.auto_close.tick()
    assert c.panel.is_open


def test_unpinning_resets_auto_close_tracking(make_controller, screen):
    pointer = _FakePointer(down=False, pos=QPoint(0, 0))
    c = make_controller(pinned=True, pointer=pointer)
    c.open_panel(screen)
    c.auto_close.tick()  # sabitken izleme çalışmaz
    c.set_pinned(False)
    pointer.down = True
    c.auto_close.tick()  # sıfırlandı: bu tıklama "açan tıklama" sayılır, kapatmaz
    assert c.panel.is_open


def test_collapsed_state_is_persisted(make_controller, tmp_path):
    c = make_controller()
    c.manager.hosts[0].toggle()
    saved = SettingsStore(tmp_path / "settings.json").load()
    assert saved.card("plain").collapsed


def test_hotkey_registered_on_start_and_failure_does_not_crash(make_controller):
    c = make_controller(hotkey="ctrl+alt+k")
    c.start()
    assert c.hotkeys.spec == "ctrl+alt+k"

    c2 = make_controller()
    c2.hotkeys.register = lambda spec: False
    c2.start()  # kısayol kaydedilemese de uygulama açılır


def test_panel_floats_with_margin_and_rounded_card(make_controller, screen):
    c = make_controller()
    c.open_panel(screen)
    work = screen.availableGeometry()
    margin = c.panel._margin
    card = c.panel.geometry()
    assert margin > 0
    assert card.top() == work.top() + margin
    assert card.bottom() == work.bottom() - margin
    assert card.right() == work.right() - margin
    # Etkileşim alanı kartı ve çevresindeki boşluğu kapsar.
    assert c.panel.target_rect().contains(card)
    assert c.look.theme.radius_panel > 0  # köşeler PanelSurface tarafından çizilir
