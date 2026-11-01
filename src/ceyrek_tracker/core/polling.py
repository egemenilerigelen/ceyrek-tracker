"""Periyodik veri çekme: her kartın kendi aralığıyla kullanabileceği genel zamanlayıcı.

Yapı:
- Zamanlayıcı ana (GUI) thread'de çalışır; ağ isteği ise her seferinde ayrı bir daemon
  thread'de yapılır, bu yüzden istek ne kadar sürerse sürsün arayüz donmaz.
- Daemon thread'in sebebi kapanıştır: bloklanan bir HTTP isteği kesilemez; daemon
  thread süreç çıkarırken kendiliğinden sonlanır, beklemek gerekmez.
- Her istek bir "nesil" numarası taşır; `set_fetch` ile kaynak değişince nesil artar
  ve eski kaynaktan geç gelen sonuç yok sayılır.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot

logger = logging.getLogger(__name__)

# Hata sonrası ilk yeniden deneme gecikmesi (saniye); her hatada ikiye katlanır.
RETRY_BASE_SECONDS = 10


def retry_delay(consecutive_failures: int, interval: int) -> int:
    """10, 20, 40 ... saniye; normal yenileme aralığını hiçbir zaman aşmaz."""
    if consecutive_failures <= 0:
        return interval
    delay = RETRY_BASE_SECONDS * 2 ** (consecutive_failures - 1)
    return min(delay, interval)


class Poller(QObject):
    """`fetch()` fonksiyonunu belirli aralıkla arka planda çağırır.

    `fetch` bir değer döndürür ya da istisna fırlatır. Sonuç `succeeded(değer)`,
    hata `failed(mesaj)` sinyaliyle ana thread'e döner.
    """

    succeeded = Signal(object)
    failed = Signal(str)

    # Arka plan thread'inden ana thread'e: (nesil, değer, hata mesajı)
    _finished = Signal(int, object, str)

    def __init__(
        self,
        fetch: Callable[[], Any],
        interval_seconds: int,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._fetch = fetch
        self._interval = interval_seconds
        self._failures = 0
        self._generation = 0
        self._in_flight = False
        self._running = False
        # Sinyal başka thread'den yayınlandığı için kuyruklu bağlantı açıkça isteniyor.
        self._finished.connect(self._on_finished, Qt.ConnectionType.QueuedConnection)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.refresh)

    @property
    def running(self) -> bool:
        return self._running

    def start(self, immediate: bool = True) -> None:
        if self._running:
            return
        self._running = True
        if immediate:
            self.refresh()
        else:
            self._schedule(self._interval)

    def stop(self) -> None:
        """Durdurur. Süren istek beklenmez; sonucu yok sayılır, böylece hemen yeniden
        başlatılabilir (panelin kapanıp açılması)."""
        self._running = False
        self._generation += 1
        self._in_flight = False
        self._timer.stop()

    @Slot()
    def refresh(self) -> None:
        """Hemen veri çeker; süren bir istek varsa yenisini başlatmaz."""
        if not self._running or self._in_flight:
            return
        self._timer.stop()
        self._in_flight = True
        threading.Thread(
            target=self._run,
            args=(self._generation, self._fetch),
            name="PollerThread",
            daemon=True,
        ).start()

    def set_fetch(self, fetch: Callable[[], Any]) -> None:
        """Kaynağı değiştirir ve hemen yeni kaynaktan veri ister."""
        self._fetch = fetch
        self._failures = 0
        self._generation += 1
        self._in_flight = False
        self.refresh()

    def set_interval(self, seconds: int) -> None:
        self._interval = seconds
        if self._running and not self._in_flight:
            self._schedule(retry_delay(self._failures, seconds))

    # --- İç işleyiş ---------------------------------------------------------

    def _run(self, generation: int, fetch: Callable[[], Any]) -> None:
        """Arka plan thread'inde çalışır; Qt nesnelerine yalnızca sinyalle dokunur."""
        value: Any = None
        error = ""
        try:
            value = fetch()
        except Exception as exc:
            logger.warning("Veri çekilemedi: %s: %s", exc.__class__.__name__, exc)
            error = str(exc) or exc.__class__.__name__
        if not self._running:
            return
        # Nesne kapanış sırasında yok edilmiş olabilir.
        with contextlib.suppress(RuntimeError):
            self._finished.emit(generation, value, error)

    def _schedule(self, seconds: int) -> None:
        if self._running:
            self._timer.start(seconds * 1000)

    @Slot(int, object, str)
    def _on_finished(self, generation: int, value: Any, error: str) -> None:
        if generation != self._generation or not self._running:
            return
        self._in_flight = False
        if error:
            self._failures += 1
            self.failed.emit(error)
            self._schedule(retry_delay(self._failures, self._interval))
        else:
            self._failures = 0
            self.succeeded.emit(value)
            self._schedule(self._interval)
