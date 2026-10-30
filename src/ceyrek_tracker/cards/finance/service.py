"""Periyodik veri çekme servisi.

Yapı:
- Zamanlayıcı ve durum yönetimi ana (GUI) thread'de, `PriceService` içinde.
- Ağ isteği her seferinde ayrı bir arka plan (daemon) thread'inde çalışır; istek ne
  kadar sürerse sürsün arayüz donmaz. Sonuç kuyruğa alınan bir sinyalle ana
  thread'e döner.
- Daemon thread kullanılmasının sebebi kapanış: bloklanan bir HTTP isteği
  kesilemez. QThread olsaydı süreç çıkarken thread'in bitmesi beklenir ya da
  nesne çalışırken yok edilip çökerdi. Daemon thread ise süreç çıkarken
  kendiliğinden sonlanır; kapanışta beklemek ya da süreci zorla öldürmek gerekmez.
- Her istek bir "nesil" numarası taşır. Kaynak değiştirilince nesil artar ve
  önceki kaynaktan geç gelen sonuç yok sayılır.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from datetime import datetime, timedelta
from typing import Protocol

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot

from ceyrek_tracker.cards.finance.models import FeedState, FeedStatus, Snapshot
from ceyrek_tracker.cards.finance.providers import AllProvidersFailed
from ceyrek_tracker.core.polling import retry_delay

logger = logging.getLogger(__name__)

# Son başarılı veri bu kadar yenileme süresinden eskiyse "gecikmeli" sayılır.
STALE_AFTER_INTERVALS = 3


class Fetcher(Protocol):
    def fetch(self) -> Snapshot: ...


def is_stale(last_success: datetime | None, interval: int, now: datetime) -> bool:
    if last_success is None:
        return True
    return now - last_success > timedelta(seconds=interval * STALE_AFTER_INTERVALS)


class PriceService(QObject):
    snapshot_changed = Signal(object)  # Snapshot
    state_changed = Signal(object)  # FeedState

    # Arka plan thread'inden ana thread'e: (nesil, snapshot | None, hatalar)
    _fetch_finished = Signal(int, object, object)

    def __init__(
        self,
        fetcher: Fetcher,
        interval_seconds: int,
        initial: Snapshot | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._fetcher = fetcher
        self._interval = interval_seconds
        self._snapshot = initial
        self._last_success: datetime | None = None
        self._failures = 0
        self._generation = 0
        self._in_flight = False
        self._running = False
        self._state = (
            FeedState(FeedStatus.STALE, "Son bilinen veri gösteriliyor")
            if initial
            else FeedState(FeedStatus.LOADING, "Veri bekleniyor")
        )

        # Sinyal başka thread'den yayınlandığı için kuyruklu bağlantı açıkça isteniyor.
        self._fetch_finished.connect(self._on_fetch_finished, Qt.ConnectionType.QueuedConnection)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.refresh)

        # Bilgisayar uykudan dönünce vb. durumlarda verinin bayatladığını yakalar.
        self._stale_check = QTimer(self)
        self._stale_check.setInterval(15_000)
        self._stale_check.timeout.connect(self._check_staleness)

    # --- Dış arayüz ---------------------------------------------------------

    @property
    def snapshot(self) -> Snapshot | None:
        return self._snapshot

    @property
    def state(self) -> FeedState:
        return self._state

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stale_check.start()
        self.state_changed.emit(self._state)
        if self._snapshot is not None:
            self.snapshot_changed.emit(self._snapshot)
        self.refresh()

    def stop(self) -> None:
        """Servisi durdurur. Süren istek beklenmez; sonucu yok sayılır."""
        self._running = False
        self._timer.stop()
        self._stale_check.stop()

    @Slot()
    def refresh(self) -> None:
        """Hemen veri çeker; süren bir istek varsa yenisini başlatmaz."""
        if not self._running or self._in_flight:
            return
        self._timer.stop()
        self._in_flight = True
        threading.Thread(
            target=self._fetch_in_background,
            args=(self._generation, self._fetcher),
            name="FetchThread",
            daemon=True,
        ).start()

    def set_fetcher(self, fetcher: Fetcher) -> None:
        """Kaynağı değiştirir ve hemen yeni kaynaktan veri ister."""
        self._fetcher = fetcher
        self._failures = 0
        # Önceki kaynaktan süren istek varsa sonucu artık geçersiz.
        self._generation += 1
        self._in_flight = False
        self.refresh()

    def set_interval(self, seconds: int) -> None:
        self._interval = seconds
        if self._running and not self._in_flight:
            self._schedule(retry_delay(self._failures, seconds))

    # --- İç işleyiş ---------------------------------------------------------

    def _fetch_in_background(self, generation: int, fetcher: Fetcher) -> None:
        """Arka plan thread'inde çalışır; Qt nesnelerine yalnızca sinyalle dokunur."""
        snapshot: Snapshot | None = None
        errors: tuple[str, ...] = ()
        try:
            snapshot = fetcher.fetch()
        except AllProvidersFailed as exc:
            errors = exc.errors
        except Exception as exc:
            logger.exception("Veri çekilirken beklenmedik hata")
            errors = (f"Beklenmedik hata: {exc.__class__.__name__}",)

        if not self._running:
            return
        # Nesne kapanış sırasında yok edilmiş olabilir.
        with contextlib.suppress(RuntimeError):
            self._fetch_finished.emit(generation, snapshot, errors)

    def _schedule(self, seconds: int) -> None:
        if self._running:
            self._timer.start(seconds * 1000)

    @Slot(int, object, object)
    def _on_fetch_finished(
        self, generation: int, snapshot: Snapshot | None, errors: tuple[str, ...]
    ) -> None:
        if generation != self._generation or not self._running:
            return
        self._in_flight = False
        if snapshot is not None:
            self._handle_success(snapshot)
        else:
            self._handle_failure(errors)

    def _handle_success(self, snapshot: Snapshot) -> None:
        self._failures = 0
        self._snapshot = snapshot
        self._last_success = snapshot.fetched_at
        logger.info("%s: %d fiyat alındı", snapshot.source_name, len(snapshot.quotes))
        self.snapshot_changed.emit(snapshot)
        self._set_state(FeedState(FeedStatus.LIVE, last_success=self._last_success))
        self._schedule(self._interval)

    def _handle_failure(self, errors: tuple[str, ...]) -> None:
        self._failures += 1
        delay = retry_delay(self._failures, self._interval)
        logger.warning(
            "Veri alınamadı (%d. hata), %ds sonra tekrar: %s",
            self._failures,
            delay,
            "; ".join(errors),
        )
        status = FeedStatus.STALE if self._snapshot else FeedStatus.OFFLINE
        self._set_state(
            FeedState(status, "Kaynaklara ulaşılamıyor", self._last_success, tuple(errors))
        )
        self._schedule(delay)

    @Slot()
    def _check_staleness(self) -> None:
        if self._state.status is not FeedStatus.LIVE:
            return
        if is_stale(self._last_success, self._interval, datetime.now()):
            self._set_state(FeedState(FeedStatus.STALE, "Veri güncel değil", self._last_success))
            self.refresh()

    def _set_state(self, state: FeedState) -> None:
        self._state = state
        self.state_changed.emit(state)
