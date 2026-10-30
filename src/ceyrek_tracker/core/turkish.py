"""Türkçe gün ve ay adları (locale'e bağımlı kalmamak için elle tanımlı)."""

from __future__ import annotations

from datetime import date

DAYS = ("Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar")
MONTHS = (
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
)


def day_name(d: date) -> str:
    return DAYS[d.weekday()]


def month_name(d: date) -> str:
    return MONTHS[d.month - 1]


def format_date(d: date) -> str:
    """'30 Ekim Cuma'"""
    return f"{d.day} {month_name(d)} {day_name(d)}"
