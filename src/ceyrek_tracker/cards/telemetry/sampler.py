"""Sistem örnekleyici: tek çağrıda tüm değerleri okur, hızları iki okuma farkından hesaplar.

Arka plan thread'inde çalışır (`Poller`). Dış bağımlılıkların hepsi kurucudan verilir; testler
gerçek sisteme, ağa ve ekran kartına dokunmaz.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any

import psutil

from ceyrek_tracker.cards.telemetry import windows
from ceyrek_tracker.cards.telemetry.gpu import NvidiaReader
from ceyrek_tracker.cards.telemetry.models import GpuReading, Sample


class Sampler:
    def __init__(
        self,
        ps: Any = psutil,
        gpu_read: Callable[[], GpuReading | None] | None = None,
        clock: Callable[[], float] = time.monotonic,
        cpu_name: Callable[[], str] = windows.cpu_name,
    ) -> None:
        self._ps = ps
        self._nvidia = None if gpu_read else NvidiaReader()
        self._gpu_read = gpu_read or self._nvidia.read
        self._clock = clock
        self._cpu_name = cpu_name()
        self._lock = threading.Lock()  # durdurulan okuma sürerken yenisi başlayabilir
        self._last_at: float | None = None
        self._last_net = (0, 0)
        self.reset()

    def reset(self) -> None:
        """Hız ölçümünün başlangıcını sıfırlar: panel uzun süre kapalı kaldıktan sonra ilk
        okuma, saatlerin ortalamasını anlık hız diye göstermesin."""
        with self._lock:
            self._ps.cpu_percent(interval=None)  # ilk çağrı anlamsız; sonrakiler aradaki farktır
            self._last_at = None

    def close(self) -> None:
        with self._lock:
            if self._nvidia is not None:
                self._nvidia.close()

    def sample(self) -> Sample:
        with self._lock:
            now = self._clock()
            memory = self._ps.virtual_memory()
            net_down, net_up = self._net_rates(now)
            return Sample(
                cpu_name=self._cpu_name,
                cpu_percent=self._ps.cpu_percent(interval=None),
                cpu_ghz=self._cpu_ghz(),
                memory_used=int(memory.total - memory.available),
                memory_total=int(memory.total),
                net_down=net_down,
                net_up=net_up,
                gpu=self._gpu_read(),
            )

    # --- İç işleyiş ---------------------------------------------------------

    def _cpu_ghz(self) -> float | None:
        try:
            current = self._ps.cpu_freq().current
        except (AttributeError, OSError, NotImplementedError):
            return None
        return current / 1000 if current else None

    def _net_rates(self, now: float) -> tuple[float, float]:
        """(ağ iniş, ağ çıkış) bayt/sn; iki okuma arasındaki farktan hesaplanır."""
        net = self._ps.net_io_counters()
        net_now = (net.bytes_recv, net.bytes_sent) if net else (0, 0)
        rates = (0.0, 0.0)
        if self._last_at is not None and now > self._last_at:
            elapsed = now - self._last_at
            down, up = (
                max(0, a - b) / elapsed for a, b in zip(net_now, self._last_net, strict=True)
            )
            rates = (down, up)
        self._last_at, self._last_net = now, net_now
        return rates
