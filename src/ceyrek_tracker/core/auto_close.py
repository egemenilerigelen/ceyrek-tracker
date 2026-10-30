"""Panelin kendiliğinden kapanması: dışarı tıklama ve farenin uzun süre panelden uzak kalması.

Sınıf yalnızca *ne zaman kapanmalı* kararını verir; paneli kendisi kapatmaz, `close_requested`
sinyali yayınlar. Fare, saat ve ayarlar dışarıdan verildiği için pencere ya da sistem olmadan
test edilebilir.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from PySide6.QtCore import QObject, QPoint, QRect, QTimer, Signal, Slot

# Panel açıkken fare/tıklama kontrolünün aralığı (ms). Durdurulunca hiç çalışmaz.
WATCH_INTERVAL_MS = 100


class Pointer(Protocol):
    def position(self) -> QPoint: ...

    def button_down(self) -> bool:
        """Fare düğmesi herhangi bir pencerede basılı mı."""
        ...


class AutoClosePolicy(Protocol):
    pinned: bool
    close_on_outside_click: bool
    leave_close_seconds: float


class PanelAutoClose(QObject):
    close_requested = Signal()

    def __init__(
        self,
        zone: Callable[[], QRect],
        policy: Callable[[], AutoClosePolicy],
        pointer: Pointer,
        clock: Callable[[], float] = time.monotonic,
        interval_ms: int = WATCH_INTERVAL_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._zone = zone
        self._policy = policy
        self._pointer = pointer
        self._clock = clock
        self._armed = False  # fare düğmesi bir kez bırakılmadan "dışarı tıklama" sayılmaz
        self._entered = False  # fare panele en az bir kez girdi mi
        self._outside_since: float | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.tick)

    def start(self) -> None:
        self.reset()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def reset(self) -> None:
        """Fare takibini sıfırdan başlatır (panel açıldığında, sabitlik kalktığında)."""
        self._armed = False
        self._entered = False
        self._outside_since = None

    @Slot()
    def tick(self) -> None:
        policy = self._policy()
        if policy.pinned:
            return
        down = self._pointer.button_down()
        if not down:
            self._armed = True
        if self._zone().contains(self._pointer.position()):
            self._entered = True
            self._outside_since = None
            return
        if down and self._armed and policy.close_on_outside_click:
            self.close_requested.emit()
            return
        leave = policy.leave_close_seconds
        if self._entered and leave > 0:
            now = self._clock()
            if self._outside_since is None:
                self._outside_since = now
            elif now - self._outside_since >= leave:
                self.close_requested.emit()
