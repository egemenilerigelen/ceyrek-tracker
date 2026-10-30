import pytest

from ceyrek_tracker.cards.finance.formatting import (
    format_change,
    format_price,
    format_tr_number,
    parse_tr_number,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("10.392,68", 10392.68),
        ("6.457", 6457.0),  # Altınkaynak ondalıksız yazıyor
        ("3.211.865", 3211865.0),
        ("$4.024,95", 4024.95),
        ("%-1,04", -1.04),
        ("%0,67", 0.67),
        ("83,83", 83.83),
        (" 12,5 ", 12.5),
        (42, 42.0),
    ],
)
def test_parse_tr_number(raw, expected):
    assert parse_tr_number(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["", "  ", "abc", "%"])
def test_parse_tr_number_rejects_garbage(raw):
    with pytest.raises(ValueError):
        parse_tr_number(raw)


def test_format_tr_number():
    assert format_tr_number(10392.68) == "10.392,68"
    assert format_tr_number(3211865) == "3.211.865,00"
    assert format_tr_number(0.5) == "0,50"


def test_format_price_currency():
    assert format_price(10392.68) == "10.392,68"
    assert format_price(4024.95, "USD") == "$4.024,95"


def test_format_change():
    assert format_change(0.67) == "▲ %0,67"
    assert format_change(-1.04) == "▼ %1,04"
    assert format_change(0.0) == "▬ %0,00"
    assert format_change(None) == "—"
