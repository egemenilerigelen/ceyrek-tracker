"""NVIDIA ekran kartı okuyucusu (NVML). Başka marka ya da sürücü yoksa sessizce devre dışı kalır.

NVML sürücüyle gelir (`nvml.dll`); yoksa ya da başlatılamazsa okuyucu bir daha denemez ve
kart GPU satırlarını göstermez. Yalnızca ilk ekran kartı okunur.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from ceyrek_tracker.cards.telemetry.models import GpuReading

logger = logging.getLogger(__name__)


def _optional(read: Callable[..., Any], *args: Any) -> Any:
    """Her kartta bulunmayan değerler (fan, güç sınırı) hata verirse None döner."""
    try:
        return read(*args)
    except Exception:
        return None


class NvidiaReader:
    def __init__(self) -> None:
        self._nvml: Any = None
        self._handle: Any = None
        self._name = ""
        self._disabled = False

    def read(self) -> GpuReading | None:
        if self._disabled:
            return None
        try:
            if self._handle is None and not self._open():
                return None
            return self._sample()
        except Exception as exc:
            # Sürücü güncellenirken ya da kart çıkarılınca okuma kopar; bir daha denenmez.
            logger.warning("GPU okunamadı, GPU satırları kapatıldı: %s", exc)
            self.close()
            self._disabled = True
            return None

    def close(self) -> None:
        if self._nvml is not None and self._handle is not None:
            _optional(self._nvml.nvmlShutdown)
        self._handle = None

    # --- İç işleyiş ---------------------------------------------------------

    def _open(self) -> bool:
        try:
            import pynvml

            pynvml.nvmlInit()
            self._nvml = pynvml
            self._handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            name = pynvml.nvmlDeviceGetName(self._handle)
            self._name = name.decode() if isinstance(name, bytes) else str(name)
        except Exception as exc:  # ImportError, NVMLError (sürücü / kart yok)
            logger.info("NVIDIA ekran kartı okunamıyor (GPU satırları gizli): %s", exc)
            self._disabled = True
            self._handle = None
            return False
        return True

    def _sample(self) -> GpuReading:
        nv, handle = self._nvml, self._handle
        memory = nv.nvmlDeviceGetMemoryInfo(handle)
        milliwatts = _optional(nv.nvmlDeviceGetPowerUsage, handle)
        limit = _optional(nv.nvmlDeviceGetEnforcedPowerLimit, handle)
        return GpuReading(
            name=self._name,
            load=float(nv.nvmlDeviceGetUtilizationRates(handle).gpu),
            memory_used=int(memory.used),
            memory_total=int(memory.total),
            temperature=_optional(nv.nvmlDeviceGetTemperature, handle, nv.NVML_TEMPERATURE_GPU),
            power_watts=None if milliwatts is None else milliwatts / 1000,
            power_limit_watts=None if limit is None else limit / 1000,
            clock_mhz=_optional(nv.nvmlDeviceGetClockInfo, handle, nv.NVML_CLOCK_GRAPHICS),
            fan_percent=_optional(nv.nvmlDeviceGetFanSpeed, handle),
        )
