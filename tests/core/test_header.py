from datetime import datetime

import pytest

from ceyrek_tracker.core.header import format_clock, format_uptime, format_uptime_line
from ceyrek_tracker.core.platform.hotkey import MOD_ALT, MOD_WIN, parse_hotkey
from ceyrek_tracker.core.turkish import format_date


def test_format_date_uses_turkish_names():
    assert format_date(datetime(2026, 10, 30).date()) == "30 Ekim Cuma"
    assert format_date(datetime(2026, 8, 3).date()) == "3 Ağustos Pazartesi"


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [(0, "0dk"), (59 * 60, "59dk"), (12 * 3600 + 48 * 60, "12s 48dk"), (50 * 3600, "2g 2s")],
)
def test_format_uptime(seconds, expected):
    assert format_uptime(seconds) == expected


def test_format_clock_and_uptime_line():
    assert format_clock(datetime(2026, 10, 30, 1, 21)) == "01:21"
    assert format_uptime_line(12 * 3600 + 48 * 60) == "Açık 12s 48dk"


def test_parse_hotkey():
    assert parse_hotkey("win+alt+w") == (MOD_WIN | MOD_ALT, ord("W"))
    assert parse_hotkey("Ctrl+F5") is not None
    assert parse_hotkey("w") is None  # değiştiricisiz kısayol olmaz
    assert parse_hotkey("win+alt+çç") is None
    assert parse_hotkey("hyper+w") is None
    assert parse_hotkey("") is None
