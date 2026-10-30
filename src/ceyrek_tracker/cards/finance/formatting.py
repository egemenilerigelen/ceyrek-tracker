"""Türkçe sayı biçimlendirme ve ayrıştırma yardımcıları."""

from __future__ import annotations

_CURRENCY_SYMBOLS = {"TRY": "", "USD": "$"}


def parse_tr_number(raw: str | float | int) -> float:
    """Kaynaklardan gelen metni float'a çevirir: "10.392,68", "6.457", "$4.024,95", "%-1,04".

    Türkçe yazımda nokta her zaman binlik ayırıcıdır, ondalık ayırıcı virgüldür.
    """
    if isinstance(raw, int | float):
        return float(raw)
    text = str(raw).strip().replace("$", "").replace("%", "").replace(" ", "")
    if not text:
        raise ValueError("boş sayı")
    return float(text.replace(".", "").replace(",", "."))


def format_tr_number(value: float, decimals: int = 2) -> str:
    """10392.68 -> "10.392,68"."""
    us = f"{value:,.{decimals}f}"
    return us.replace(",", "\0").replace(".", ",").replace("\0", ".")


def format_price(value: float, currency: str = "TRY") -> str:
    return f"{_CURRENCY_SYMBOLS.get(currency, '')}{format_tr_number(value)}"


def format_change(change_pct: float | None) -> str:
    if change_pct is None:
        return "—"
    if change_pct > 0:
        return f"▲ %{format_tr_number(change_pct)}"
    if change_pct < 0:
        return f"▼ %{format_tr_number(abs(change_pct))}"
    return f"▬ %{format_tr_number(0)}"
