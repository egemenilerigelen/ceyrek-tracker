"""Telemetri verisi: arka plan thread'inde üretilir, ana thread'de yalnızca okunur."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GpuReading:
    name: str
    load: float  # yüzde
    memory_used: int  # bayt
    memory_total: int
    temperature: float | None = None  # °C
    power_watts: float | None = None
    power_limit_watts: float | None = None
    clock_mhz: int | None = None
    fan_percent: int | None = None


@dataclass(frozen=True)
class Sample:
    cpu_name: str
    cpu_percent: float
    cpu_ghz: float | None
    memory_used: int
    memory_total: int
    net_down: float  # bayt/sn
    net_up: float
    gpu: GpuReading | None  # desteklenen bir ekran kartı yoksa None

    @property
    def memory_percent(self) -> float:
        return 100 * self.memory_used / self.memory_total if self.memory_total else 0.0
