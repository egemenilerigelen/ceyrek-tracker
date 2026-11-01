"""Telemetri kartı: işlemci, bellek, ekran kartı ve ağın canlı durumu.

Her gösterge bir satırdır: simge ve ad, çizgi grafik ya da doluluk çubuğu, renkli değer ve
altında sönük bir ayrıntı satırı. Veri panel açıkken saniyede bir okunur; panel kapanınca
(ya da kart katlanınca) okuma durur, boşta işlemci kullanılmaz. Ağ gecikmesi (ping) ayrı bir
yoklamayla okunur: yanıtsız bir sunucu diğer değerleri bekletmesin.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QVBoxLayout

from ceyrek_tracker.cards.telemetry import icon as icons
from ceyrek_tracker.cards.telemetry.formatting import (
    bit_rate,
    gb_pair,
    ghz,
    percent,
    short_cpu_name,
    short_gpu_name,
)
from ceyrek_tracker.cards.telemetry.models import Sample
from ceyrek_tracker.cards.telemetry.ping import tcp_ping
from ceyrek_tracker.cards.telemetry.sampler import Sampler
from ceyrek_tracker.cards.telemetry.widgets import HISTORY, Meter, MetricRow, Sparkline
from ceyrek_tracker.core.card_base import Card, CardContext, CardSpec, guarded
from ceyrek_tracker.core.polling import Poller
from ceyrek_tracker.theme import Look

REFRESH_SECONDS = 1
HEADER_GLYPH = ""  # Segoe MDL2 Assets; başlıkta bunun yerine çizilen simge kullanılır

# Doluluk eşikleri (%): üstünde değer ve grafik uyarı, sonra tehlike rengine döner.
WARN_AT = 75
DOWN_AT = 90
PING_WARN_MS = 100
PING_DOWN_MS = 250
PING_MAX_SHOWN = 999

# Grafiğin en az kapsadığı değer: neredeyse boşta bir değer çizgiyi tavana yapıştırmasın.
CPU_FLOOR = 25.0
PING_FLOOR = 50.0

EMPTY = "—"


@dataclass(frozen=True)
class RowSpec:
    title: str
    icon: str
    graph: str  # "line" ya da "bar"
    tone: str


ROWS: dict[str, RowSpec] = {
    "cpu": RowSpec("İşlemci", icons.CPU, "line", "blue"),
    "ram": RowSpec("Bellek (RAM)", icons.MEMORY, "bar", "cyan"),
    "gpu": RowSpec("Ekran Kartı", icons.GPU, "line", "blue"),
    "vram": RowSpec("Video Belleği", icons.VRAM, "bar", "cyan"),
    "gpu_power": RowSpec("GPU Güç", icons.POWER, "bar", "violet"),
    "net": RowSpec("Ağ", icons.NETWORK, "line", "green"),
}
GPU_ROWS = ("gpu", "vram", "gpu_power")  # NVIDIA ekran kartı yoksa gizlenir
DEFAULT_ITEMS = tuple(ROWS)


def parse_items(raw: Any) -> tuple[str, ...]:
    """Ayardaki satır listesi: bilinmeyenler (kaldırılan `disk_io`, `drives` dahil) ve tekrarlar
    atılır, geçerli bir şey kalmazsa varsayılan liste kullanılır."""
    if isinstance(raw, list):
        ids = dict.fromkeys(i for i in raw if isinstance(i, str) and i in ROWS)
        if ids:
            return tuple(ids)
    return DEFAULT_ITEMS


def level_tone(value: float, base: str) -> str:
    """Doluluk yüzdesinin rengi: normalde satırın tonu, yüksekse uyarı ve tehlike."""
    if value >= DOWN_AT:
        return "down"
    return "warn" if value >= WARN_AT else base


def ping_tone(ms: float | None, base: str) -> str:
    if ms is None or ms >= PING_DOWN_MS:
        return "down"
    return "warn" if ms >= PING_WARN_MS else base


class TelemetryCard(Card):
    def __init__(
        self,
        context: CardContext,
        sampler: Sampler | None = None,
        ping: Callable[[], float | None] | None = None,
    ) -> None:
        super().__init__(context)
        self._items = parse_items(self.config.get("items"))
        self._sampler = sampler or Sampler()
        self._history: dict[str, deque[float | None]] = {
            key: deque(maxlen=HISTORY) for key in ("cpu", "gpu", "ping")
        }
        self._sample: Sample | None = None
        self._ping_ms: float | None = None
        self._rows: dict[str, MetricRow] = {}
        self._shown = False
        self._collapsed = False
        self._build_ui()

        self._poller = Poller(self._sampler.sample, REFRESH_SECONDS, self)
        self._poller.succeeded.connect(self._on_sample)
        self._poller.failed.connect(self._on_failure)
        self._ping_poller = Poller(ping or tcp_ping, REFRESH_SECONDS, self)
        self._ping_poller.succeeded.connect(self._on_ping)

    # --- Arayüz -------------------------------------------------------------

    def _make_row(self, spec: RowSpec) -> MetricRow:
        graph = Sparkline(self.look) if spec.graph == "line" else Meter(self.look)
        return MetricRow(spec.title, spec.icon, graph, self.look, spec.tone)

    def _build_ui(self) -> None:
        sp = self.look.metrics.sp
        rows = QVBoxLayout(self)  # kutu yok: satırlar panel zemininde durur (finans kartı gibi)
        rows.setContentsMargins(sp(2), 0, sp(2), sp(2))
        rows.setSpacing(sp(8))
        for key in self._items:
            row = self._make_row(ROWS[key])
            row.setVisible(key not in GPU_ROWS)  # ekran kartı okununca görünür
            self._rows[key] = row
            rows.addWidget(row)

    # --- Veri ---------------------------------------------------------------

    @guarded
    def _on_sample(self, sample: Sample) -> None:
        if self.current_error:
            self.clear_error()
        self._sample = sample
        self._history["cpu"].append(sample.cpu_percent)
        if sample.gpu is not None:
            self._history["gpu"].append(sample.gpu.load)
        self._render(sample)

    @guarded
    def _on_ping(self, ms: float | None) -> None:
        self._ping_ms = ms
        self._history["ping"].append(ms)
        if self._sample is not None:
            self._paint_net(self._sample)

    @guarded
    def _on_failure(self, message: str) -> None:
        self.fail("Sistem bilgisi okunamıyor")

    def _render(self, s: Sample) -> None:
        painters = {
            "cpu": self._paint_cpu,
            "ram": self._paint_ram,
            "gpu": self._paint_gpu,
            "vram": self._paint_vram,
            "gpu_power": self._paint_gpu_power,
            "net": self._paint_net,
        }
        for key in self._rows:
            painters[key](s)

    def _line(self, key: str, history: str, floor: float) -> None:
        self._rows[key].graph.set_values(list(self._history[history]), floor=floor)

    def _paint_cpu(self, s: Sample) -> None:
        name = short_cpu_name(s.cpu_name)
        detail = ghz(s.cpu_ghz) if s.cpu_ghz else name
        tone = level_tone(s.cpu_percent, ROWS["cpu"].tone)
        self._rows["cpu"].set_view(detail, percent(s.cpu_percent), tone, f"{name} · {detail}")
        self._line("cpu", "cpu", CPU_FLOOR)

    def _paint_ram(self, s: Sample) -> None:
        tone = level_tone(s.memory_percent, ROWS["ram"].tone)
        row = self._rows["ram"]
        full = gb_pair(s.memory_used, s.memory_total)
        row.set_view(
            gb_pair(s.memory_used, s.memory_total, compact=True),
            percent(s.memory_percent),
            tone,
            full,
        )
        row.graph.set_fraction(s.memory_percent / 100)

    def _paint_gpu(self, s: Sample) -> None:
        row, gpu = self._rows["gpu"], s.gpu
        row.setVisible(gpu is not None)
        if gpu is None:
            return
        name = short_gpu_name(gpu.name)
        temperature = None if gpu.temperature is None else f"{round(gpu.temperature)}°C"
        row.set_view(
            temperature or name,
            percent(gpu.load),
            level_tone(gpu.load, ROWS["gpu"].tone),
            f"{name} · {temperature}" if temperature else name,
        )
        self._line("gpu", "gpu", CPU_FLOOR)

    def _paint_vram(self, s: Sample) -> None:
        row, gpu = self._rows["vram"], s.gpu
        present = gpu is not None and gpu.memory_total > 0
        row.setVisible(present)
        if not present:
            return
        used = 100 * gpu.memory_used / gpu.memory_total
        row.set_view(
            gb_pair(gpu.memory_used, gpu.memory_total, compact=True),
            percent(used),
            level_tone(used, ROWS["vram"].tone),
            gb_pair(gpu.memory_used, gpu.memory_total),
        )
        row.graph.set_fraction(used / 100)

    def _paint_gpu_power(self, s: Sample) -> None:
        row, gpu = self._rows["gpu_power"], s.gpu
        present = gpu is not None and gpu.power_watts is not None
        row.setVisible(present)
        if not present:
            return
        parts = []
        if gpu.clock_mhz is not None:
            parts.append(f"{gpu.clock_mhz} MHz")
        if gpu.fan_percent is not None:
            parts.append(f"Fan {percent(gpu.fan_percent)}")
        row.set_view(
            parts[0] if parts else "",
            f"{round(gpu.power_watts)} W",
            ROWS["gpu_power"].tone,
            " · ".join(parts),
        )
        limit = gpu.power_limit_watts
        row.graph.set_fraction(gpu.power_watts / limit if limit else 0.0)

    def _paint_net(self, s: Sample) -> None:
        ms = self._ping_ms
        value = EMPTY if ms is None else f"{round(min(ms, PING_MAX_SHOWN))} ms"
        detail = f"↓{bit_rate(s.net_down, compact=True)} ↑{bit_rate(s.net_up, compact=True)}"
        full = f"↓ {bit_rate(s.net_down)} ↑ {bit_rate(s.net_up)}"
        self._rows["net"].set_view(detail, value, ping_tone(ms, ROWS["net"].tone), full)
        self._line("net", "ping", PING_FLOOR)

    # --- Yaşam döngüsü ------------------------------------------------------

    def on_show(self) -> None:
        self._shown = True
        self._sync_polling()

    def on_hide(self) -> None:
        self._shown = False
        self._sync_polling()

    def on_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._sync_polling()

    def _sync_polling(self) -> None:
        """Yalnızca panel açıkken ve kart katlı değilken okur."""
        if self._shown and not self._collapsed:
            if not self._poller.running:
                # Uzun kapalılıktan sonra ilk okuma, saatlerin ortalamasını hız diye göstermesin.
                self._sampler.reset()
                for history in self._history.values():
                    history.clear()
                self._poller.start()
                self._ping_poller.start()
        else:
            self._poller.stop()
            self._ping_poller.stop()

    def set_look(self, look: Look) -> None:
        super().set_look(look)
        for row in self._rows.values():
            row.set_look(look)

    def shutdown(self) -> None:
        self._poller.stop()
        self._ping_poller.stop()
        self._sampler.close()


def _create(context: CardContext) -> Card:
    return TelemetryCard(context)


SPEC = CardSpec(
    id="telemetry",
    title="Telemetri",
    icon=HEADER_GLYPH,
    factory=_create,
    icon_factory=icons.header_icon,
)

__all__ = ["SPEC", "TelemetryCard"]
