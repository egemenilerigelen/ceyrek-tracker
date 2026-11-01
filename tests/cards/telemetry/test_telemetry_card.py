import contextlib

import pytest

from ceyrek_tracker.cards import CARDS, telemetry
from ceyrek_tracker.cards.telemetry.card import (
    DEFAULT_ITEMS,
    level_tone,
    parse_items,
    ping_tone,
)
from ceyrek_tracker.cards.telemetry.models import GpuReading, Sample
from ceyrek_tracker.cards.telemetry.widgets import HISTORY
from ceyrek_tracker.core.card_base import CardContext
from ceyrek_tracker.core.card_host import CardHost
from ceyrek_tracker.theme import resolve_look

LOOK = resolve_look("dark", "normal", 1.0)
GB = 1024**3


def make_sample(cpu=4.0, gpu="default"):
    if gpu == "default":
        gpu = GpuReading(
            "NVIDIA GeForce RTX 5060",
            3,
            int(1.6 * GB),
            8 * GB,
            temperature=41,
            power_watts=18.4,
            power_limit_watts=145,
            clock_mhz=577,
            fan_percent=0,
        )
    return Sample(
        cpu_name="AMD Ryzen 5 7500F 6-Core Processor",
        cpu_percent=cpu,
        cpu_ghz=4.68,
        memory_used=int(15.2 * GB),
        memory_total=int(31.6 * GB),
        net_down=750,
        net_up=860,
        gpu=gpu,
    )


class FakeSampler:
    def __init__(self, sample=None):
        self.next = sample or make_sample()
        self.resets = 0
        self.closed = False

    def sample(self):
        return self.next

    def reset(self):
        self.resets += 1

    def close(self):
        self.closed = True


@pytest.fixture
def make_card(qtbot):
    cards = []

    def make(config=None, sampler=None, ping=lambda: 34.0):
        card = telemetry.TelemetryCard(
            CardContext(LOOK, config or {}), sampler or FakeSampler(), ping
        )
        qtbot.addWidget(card)
        card.show()
        cards.append(card)
        return card

    yield make
    for card in cards:
        with contextlib.suppress(RuntimeError):  # pytest-qt pencereleri önce silmiş olabilir
            card.shutdown()


def show(card, sample=None, ping=34.0):
    """Arka plan thread'i olmadan bir okuma işler."""
    card._on_ping(ping)
    card._on_sample(sample or make_sample())


def row(card, key):
    return card._rows[key]


# --- Ayar ve eşikler -------------------------------------------------------


def test_default_rows_follow_the_reference_layout(make_card):
    card = make_card()
    assert list(card._rows) == ["cpu", "ram", "gpu", "vram", "gpu_power", "net"]
    assert tuple(card._rows) == DEFAULT_ITEMS


def test_rows_follow_configured_items(make_card):
    card = make_card({"items": ["net", "cpu", "bilinmeyen", "cpu"]})
    assert list(card._rows) == ["net", "cpu"]


def test_invalid_items_fall_back_to_default():
    assert parse_items(None) == DEFAULT_ITEMS
    assert parse_items([]) == DEFAULT_ITEMS
    assert parse_items(["yok", 3]) == DEFAULT_ITEMS
    assert parse_items(["ram", "cpu"]) == ("ram", "cpu")


def test_removed_disk_rows_in_old_settings_are_ignored():
    assert parse_items(["cpu", "disk_io", "drives", "ram"]) == ("cpu", "ram")
    assert parse_items(["disk_io", "drives"]) == DEFAULT_ITEMS


@pytest.mark.parametrize(
    ("value", "tone"), [(0, "blue"), (74.9, "blue"), (75, "warn"), (89.9, "warn"), (90, "down")]
)
def test_level_tone(value, tone):
    assert level_tone(value, "blue") == tone


@pytest.mark.parametrize(
    ("ms", "tone"), [(20, "green"), (99, "green"), (100, "warn"), (250, "down"), (None, "down")]
)
def test_ping_tone(ms, tone):
    assert ping_tone(ms, "green") == tone


def test_card_is_registered_and_enabled_by_default():
    assert telemetry.SPEC in CARDS
    assert telemetry.SPEC.default_enabled


# --- Görünüm ---------------------------------------------------------------


def test_rows_show_short_details_and_full_tooltips(make_card):
    card = make_card()
    show(card)
    cpu, ram, gpu = row(card, "cpu"), row(card, "ram"), row(card, "gpu")
    assert (cpu.title(), cpu.detail(), cpu.value()) == ("İşlemci", "4,68 GHz", "%4")
    assert cpu.toolTip() == "Ryzen 5 7500F · 4,68 GHz"
    assert (ram.detail(), ram.value(), ram.toolTip()) == (
        "15,2/31,6 GB",
        "%48",
        "15,2 / 31,6 GB",
    )
    assert (gpu.detail(), gpu.value(), gpu.toolTip()) == ("41°C", "%3", "RTX 5060 · 41°C")
    vram, power = row(card, "vram"), row(card, "gpu_power")
    assert (vram.detail(), vram.value(), vram.toolTip()) == (
        "1,6/8,0 GB",
        "%20",
        "1,6 / 8,0 GB",
    )
    assert (power.detail(), power.value(), power.toolTip()) == (
        "577 MHz",
        "18 W",
        "577 MHz · Fan %0",
    )
    net = row(card, "net")
    assert (net.detail(), net.value(), net.toolTip()) == (
        "↓6K ↑7K",
        "34 ms",
        "↓ 6 Kbps ↑ 7 Kbps",
    )


def test_bars_follow_the_fractions(make_card):
    card = make_card()
    show(card)
    assert row(card, "ram").graph.fraction() == pytest.approx(0.481, abs=0.01)
    assert row(card, "vram").graph.fraction() == pytest.approx(0.2, abs=0.01)
    assert row(card, "gpu_power").graph.fraction() == pytest.approx(18.4 / 145)


def test_gpu_rows_are_hidden_without_a_supported_gpu(make_card):
    card = make_card()
    assert all(not row(card, key).isVisibleTo(card) for key in ("gpu", "vram", "gpu_power"))
    show(card, make_sample(gpu=None))
    assert all(not row(card, key).isVisibleTo(card) for key in ("gpu", "vram", "gpu_power"))
    assert row(card, "cpu").isVisibleTo(card)


def test_gpu_rows_appear_with_a_gpu(make_card):
    card = make_card()
    show(card)
    assert all(row(card, key).isVisibleTo(card) for key in ("gpu", "vram", "gpu_power"))


def test_power_row_is_hidden_when_the_card_reports_no_power(make_card):
    gpu = GpuReading("NVIDIA GeForce GT 710", 0, 1 * GB, 2 * GB)
    card = make_card()
    show(card, make_sample(gpu=gpu))
    assert row(card, "gpu").isVisibleTo(card)
    assert not row(card, "gpu_power").isVisibleTo(card)
    assert row(card, "gpu").detail() == "GT 710"  # sıcaklık okunamadı: ad görünür


def test_power_detail_omits_unsupported_readings(make_card):
    gpu = GpuReading("NVIDIA GeForce RTX 4060", 0, GB, 8 * GB, power_watts=12, clock_mhz=210)
    card = make_card()
    show(card, make_sample(gpu=gpu))
    assert row(card, "gpu_power").detail() == "210 MHz"
    assert row(card, "gpu_power").toolTip() == "210 MHz"
    assert row(card, "gpu_power").graph.fraction() == 0  # güç sınırı bilinmiyor


def test_high_load_turns_value_and_graph_warm(make_card):
    card = make_card()
    show(card, make_sample(cpu=95))
    assert row(card, "cpu").tone() == "down"
    assert row(card, "cpu")._value.property("tone") == "down"
    show(card, make_sample(cpu=80))
    assert row(card, "cpu").tone() == "warn"
    show(card, make_sample(cpu=5))
    assert row(card, "cpu").tone() == "blue"


def test_unreachable_network_shows_dash_and_danger_tone(make_card):
    card = make_card()
    show(card, ping=None)
    assert row(card, "net").value() == "—"
    assert row(card, "net").tone() == "down"
    assert row(card, "net").graph.values()[-1] is None  # çizgide boşluk


def test_ping_is_clamped_to_the_value_column(make_card):
    card = make_card()
    show(card, ping=4321.0)
    assert row(card, "net").value() == "999 ms"


def test_ping_update_repaints_without_waiting_for_a_sample(make_card):
    card = make_card()
    show(card)
    card._on_ping(180.0)
    assert row(card, "net").value() == "180 ms"
    assert row(card, "net").tone() == "warn"


def test_ping_before_the_first_sample_is_remembered(make_card):
    card = make_card()
    card._on_ping(40.0)
    assert card._sample is None
    card._on_sample(make_sample())
    assert row(card, "net").value() == "40 ms"


def test_history_is_bounded_and_drawn(make_card):
    card = make_card()
    for i in range(HISTORY + 20):
        show(card, make_sample(cpu=i % 50))
    assert len(card._history["cpu"]) == HISTORY
    assert len(row(card, "cpu").graph.values()) == HISTORY


# --- Hata ve yaşam döngüsü -------------------------------------------------


def test_failure_is_shown_in_the_card_and_cleared_by_the_next_sample(make_card):
    card = make_card()
    card._on_failure("psutil bozuldu")
    assert card.current_error == "Sistem bilgisi okunamıyor"
    show(card)
    assert card.current_error == ""


def test_polling_runs_only_while_panel_is_open(qtbot, make_card):
    sampler = FakeSampler()
    card = make_card(sampler=sampler)
    assert not card._poller.running
    card.on_show()
    assert card._poller.running
    assert card._ping_poller.running
    qtbot.waitUntil(lambda: card._sample is not None, timeout=3000)
    card.on_hide()
    assert not card._poller.running
    assert not card._ping_poller.running


def test_collapsed_card_does_not_poll(make_card):
    card = make_card()
    card.on_collapsed(True)
    card.on_show()
    assert not card._poller.running
    card.on_collapsed(False)
    assert card._poller.running
    card.on_collapsed(True)
    assert not card._poller.running


def test_reopening_resets_rates_and_history(make_card):
    sampler = FakeSampler()
    card = make_card(sampler=sampler)
    show(card)
    assert card._history["cpu"]
    card.on_show()
    assert sampler.resets == 1
    assert not card._history["cpu"]
    card.on_show()  # zaten açık: yeniden sıfırlanmaz
    assert sampler.resets == 1


def test_reopening_works_even_if_a_read_was_in_flight(qtbot, make_card):
    card = make_card()
    card.on_show()
    card.on_hide()
    card._sample = None
    card.on_show()
    qtbot.waitUntil(lambda: card._sample is not None, timeout=3000)


def test_shutdown_stops_polling_and_closes_the_sampler(make_card):
    sampler = FakeSampler()
    card = make_card(sampler=sampler)
    card.on_show()
    card.shutdown()
    assert not card._poller.running
    assert sampler.closed


def test_look_change_is_applied_to_rows(make_card):
    card = make_card()
    show(card)
    light = resolve_look("light", "normal", 1.0)
    card.set_look(light)
    assert row(card, "cpu").graph._color.name() == light.theme.tone_color("blue")
    assert row(card, "net").graph._color.name() == light.theme.tone_color("green")


def test_card_renders_inside_host_without_error(qtbot):
    # Kart çerçevenin çocuğu olur; çerçeve silinince kart da silinir, ayrıca kaydedilmez.
    card = telemetry.TelemetryCard(CardContext(LOOK, {}), FakeSampler(), lambda: 34.0)
    host = CardHost(telemetry.SPEC, card, LOOK, animate=False)
    qtbot.addWidget(host)
    host.show()
    show(card)
    assert host._error.isHidden()
    assert not host.grab().isNull()
    card.shutdown()
