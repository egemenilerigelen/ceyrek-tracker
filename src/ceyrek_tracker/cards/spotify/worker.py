"""Kartın tek arka plan thread'i: Windows'a (COM / WinRT) yapılan tüm çağrılar burada sırayla işler.

Neden tek ve uzun ömürlü thread: COM nesneleri ve WinRT çağrıları kurulduğu thread'e
bağlıdır; her işte yeni thread açmak her seferinde COM'u baştan kurmayı gerektirir. Tek
thread ayrıca komutlarla yoklamayı sıraya sokar (ör. "ileri" komutundan sonra okuma, yeni
şarkıyı görür). Thread daemon'dur: bloklanan bir çağrı uygulamanın kapanmasını geciktirmez.
"""

from __future__ import annotations

import contextlib
import logging
import queue
import threading
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal, Slot

logger = logging.getLogger(__name__)


class Worker(QObject):
    """`submit(etiket, iş)`: iş arka planda çalışır, sonuç `done(etiket, değer, hata)` ile ana
    thread'e döner. Hata varsa hata metni doludur (boş = başarılı)."""

    done = Signal(str, object, str)
    _finished = Signal(str, object, str)  # arka plan thread'inden ana thread'e

    def __init__(self, prepare: Callable[[], None] | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._prepare = prepare
        self._jobs: queue.Queue[tuple[str, Callable[[], Any]] | None] = queue.Queue()
        self._alive = True
        # Sinyal başka thread'den yayınlandığı için kuyruklu bağlantı açıkça isteniyor.
        self._finished.connect(self._relay, Qt.ConnectionType.QueuedConnection)
        self._thread = threading.Thread(target=self._loop, name="SpotifyWorker", daemon=True)
        self._thread.start()

    def submit(self, tag: str, job: Callable[[], Any]) -> None:
        if self._alive:
            self._jobs.put((tag, job))

    def stop(self) -> None:
        """Durdurur. Süren iş beklenmez; sonucu yok sayılır."""
        self._alive = False
        self._jobs.put(None)

    @Slot(str, object, str)
    def _relay(self, tag: str, value: Any, error: str) -> None:
        if self._alive:
            self.done.emit(tag, value, error)

    def _loop(self) -> None:
        """Arka plan thread'inde çalışır; Qt nesnelerine yalnızca sinyalle dokunur."""
        if self._prepare is not None:
            try:
                self._prepare()
            except Exception:
                logger.exception("Spotify arka plan thread'i hazırlanamadı")
        while True:
            item = self._jobs.get()
            if item is None or not self._alive:
                return
            tag, job = item
            value: Any = None
            error = ""
            try:
                value = job()
            except Exception as exc:
                logger.warning("Spotify işi '%s' başarısız: %s: %s", tag, type(exc).__name__, exc)
                error = str(exc) or type(exc).__name__
            # Nesne kapanış sırasında yok edilmiş olabilir.
            with contextlib.suppress(RuntimeError):
                self._finished.emit(tag, value, error)
