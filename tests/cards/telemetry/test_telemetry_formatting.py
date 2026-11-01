import pytest

from ceyrek_tracker.cards.telemetry.formatting import (
    GB,
    bit_rate,
    gb_pair,
    ghz,
    percent,
    short_cpu_name,
    short_gpu_name,
)


@pytest.mark.parametrize(
    ("raw", "short"),
    [
        ("AMD Ryzen 5 7500F 6-Core Processor", "Ryzen 5 7500F"),
        ("11th Gen Intel(R) Core(TM) i3-1115G4 @ 3.00GHz", "Core i3-1115G4"),
        ("Intel(R) Core(TM) i9-14900K", "Core i9-14900K"),
        ("Bilinmeyen İşlemci", "Bilinmeyen İşlemci"),
        ("Intel(R) CPU", "Intel(R) CPU"),  # her şey sökülürse özgün ad kalır
    ],
)
def test_cpu_name_is_shortened(raw, short):
    assert short_cpu_name(raw) == short


@pytest.mark.parametrize(
    ("raw", "short"),
    [
        ("NVIDIA GeForce RTX 5060", "RTX 5060"),
        ("NVIDIA GeForce RTX 4070 Laptop GPU", "RTX 4070"),
        ("Radeon RX 7800 XT", "Radeon RX 7800 XT"),
    ],
)
def test_gpu_name_is_shortened(raw, short):
    assert short_gpu_name(raw) == short


def test_percent_rounds_and_uses_turkish_prefix():
    assert percent(3.4) == "%3"
    assert percent(47.5) == "%48"
    assert percent(100) == "%100"


def test_memory_pair_uses_one_decimal_for_both():
    assert gb_pair(15.2 * GB, 31.6 * GB) == "15,2 / 31,6 GB"
    assert gb_pair(1.6 * GB, 8 * GB) == "1,6 / 8,0 GB"


@pytest.mark.parametrize(
    ("bytes_per_second", "text"),
    [
        (10, "80 bps"),
        (750, "6 Kbps"),
        (1.5e6 / 8, "1,5 Mbps"),
        (200e6 / 8, "200 Mbps"),
        (1.3e9 / 8, "1,3 Gbps"),
    ],
)
def test_bit_rate_is_in_bits(bytes_per_second, text):
    assert bit_rate(bytes_per_second) == text


def test_compact_forms_drop_spaces_and_suffixes():
    assert gb_pair(15.2 * GB, 31.6 * GB, compact=True) == "15,2/31,6 GB"
    assert bit_rate(750, compact=True) == "6K"
    assert bit_rate(200e6 / 8, compact=True) == "200M"
    assert bit_rate(10, compact=True) == "80b"


def test_ghz_uses_decimal_comma():
    assert ghz(4.68) == "4,68 GHz"
