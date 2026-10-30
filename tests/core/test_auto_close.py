import pytest
from PySide6.QtCore import QPoint, QRect

from ceyrek_tracker.core.auto_close import PanelAutoClose

ZONE = QRect(100, 0, 300, 800)
INSIDE, OUTSIDE = QPoint(200, 400), QPoint(0, 0)


class _Policy:
    def __init__(self, pinned=False, close_on_outside_click=True, leave_close_seconds=3.0):
        self.pinned = pinned
        self.close_on_outside_click = close_on_outside_click
        self.leave_close_seconds = leave_close_seconds


class _Pointer:
    def __init__(self, pos=OUTSIDE, down=False):
        self.pos = pos
        self.down = down

    def position(self):
        return self.pos

    def button_down(self):
        return self.down


@pytest.fixture
def make(qapp):
    """(izleyici, fare, saat, kapatma istekleri) üretir; sistem ve gerçek saat gerekmez."""

    def build(policy=None, pointer=None):
        pointer = pointer or _Pointer()
        clock = {"t": 100.0}
        watcher = PanelAutoClose(
            zone=lambda: ZONE,
            policy=lambda: policy or _Policy(),
            pointer=pointer,
            clock=lambda: clock["t"],
        )
        requests = []
        watcher.close_requested.connect(lambda: requests.append(1))
        return watcher, pointer, clock, requests

    return build


def test_outside_click_counts_only_after_buttons_were_released(make):
    watcher, pointer, _, requests = make(pointer=_Pointer(OUTSIDE, down=True))
    watcher.tick()  # paneli açan tıklama hâlâ basılı
    assert not requests
    pointer.down = False
    watcher.tick()
    pointer.down = True
    watcher.tick()  # panel dışında yeni tıklama
    assert requests == [1]


def test_click_inside_never_closes(make):
    watcher, pointer, _, requests = make(pointer=_Pointer(INSIDE))
    watcher.tick()
    pointer.down = True
    watcher.tick()
    assert not requests


def test_outside_click_can_be_disabled(make):
    watcher, pointer, _, requests = make(policy=_Policy(close_on_outside_click=False))
    watcher.tick()
    pointer.down = True
    watcher.tick()
    assert not requests


def test_pinned_panel_is_never_closed(make):
    watcher, pointer, _, requests = make(policy=_Policy(pinned=True), pointer=_Pointer(down=True))
    watcher.tick()
    pointer.down = False
    watcher.tick()
    pointer.down = True
    watcher.tick()
    assert not requests


def test_leave_timeout_starts_only_after_mouse_entered(make):
    watcher, pointer, clock, requests = make(
        policy=_Policy(close_on_outside_click=False, leave_close_seconds=2.0)
    )
    for _ in range(3):  # fare hiç girmediyse (kısayolla açıldı) kapanmaz
        clock["t"] += 5
        watcher.tick()
    assert not requests

    pointer.pos = INSIDE
    watcher.tick()  # içeri girdi
    pointer.pos = OUTSIDE
    watcher.tick()  # dışarı çıktı, sayaç başlar
    clock["t"] += 1.0
    watcher.tick()
    assert not requests
    clock["t"] += 1.5
    watcher.tick()
    assert requests == [1]


def test_returning_inside_cancels_the_leave_timer(make):
    watcher, pointer, clock, requests = make(
        policy=_Policy(close_on_outside_click=False, leave_close_seconds=2.0)
    )
    pointer.pos = INSIDE
    watcher.tick()
    pointer.pos = OUTSIDE
    watcher.tick()
    clock["t"] += 1.5
    pointer.pos = INSIDE
    watcher.tick()  # geri döndü
    pointer.pos = OUTSIDE
    watcher.tick()  # sayaç yeniden başlar
    clock["t"] += 1.5
    watcher.tick()
    assert not requests


def test_reset_forgets_entered_and_armed_state(make):
    watcher, pointer, clock, requests = make(
        policy=_Policy(close_on_outside_click=False, leave_close_seconds=1.0)
    )
    pointer.pos = INSIDE
    watcher.tick()
    watcher.reset()
    pointer.pos = OUTSIDE
    watcher.tick()
    clock["t"] += 5
    watcher.tick()  # içeri girmişlik unutuldu: kapanmaz
    assert not requests
