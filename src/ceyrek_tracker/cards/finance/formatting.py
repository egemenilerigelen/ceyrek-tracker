"""Türkçe sayı biçimlendirme ve ayrıştırma yardımcıları."""

from __future__ import annotations

# para birimi -> (önek, sonek)
_CURRENCY_AFFIXES = {"TRY": ("", " ₺"), "USD": ("$", "")}


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
    """49.96 -> "49,96 ₺"; binlik ve üstünde kuruş yazılmaz: 10274.06 -> "10.274 ₺"."""
    prefix, suffix = _CURRENCY_AFFIXES.get(currency, ("", ""))
    decimals = 0 if abs(value) >= 1000 else 2
    return f"{prefix}{format_tr_number(value, decimals)}{suffix}"


def format_change(change_pct: float | None) -> str:
    """0.07 -> "%0,07", -1.04 -> "%-1,04"; yön rengi arayüzde verilir."""
    if change_pct is None:
        return "—"
    return f"%{format_tr_number(round(change_pct, 2) + 0.0)}"  # "-0,00" çıkmasın
