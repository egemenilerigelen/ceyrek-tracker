"""Türkçe sayı ve birim biçimleri: ondalık virgül, boşluklu birim ("15,2 GB", "6 Kbps")."""

from __future__ import annotations

import re

GB = 1024**3


def number(value: float, decimals: int = 0) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def percent(value: float) -> str:
    return f"%{round(value)}"


def gb_pair(used: float, total: float, compact: bool = False) -> str:
    """ "15,2 / 31,6 GB"; `compact` ile dar yerler için "15,2/31,6 GB"."""
    joiner = "/" if compact else " / "
    return f"{number(used / GB, 1)}{joiner}{number(total / GB, 1)} GB"


def bit_rate(bytes_per_second: float, compact: bool = False) -> str:
    """Ağ hızı bit olarak: "6 Kbps", "12,4 Mbps"; `compact` ile dar yerler için "6K", "12,4M"."""
    bits = bytes_per_second * 8
    for factor, unit in ((1e9, "Gbps"), (1e6, "Mbps"), (1e3, "Kbps")):
        if bits >= factor:
            value = bits / factor
            text = number(value, 1 if unit != "Kbps" and value < 100 else 0)
            return f"{text}{unit[0]}" if compact else f"{text} {unit}"
    return f"{round(bits)}b" if compact else f"{round(bits)} bps"


def ghz(value: float) -> str:
    return f"{number(value, 2)} GHz"


_CPU_NOISE = re.compile(
    r"\((?:R|TM)\)|\bCPU\b|@\s*[\d.]+\s*GHz|\b\d+-Core Processor\b|\bProcessor\b|"
    r"\b\d+(?:st|nd|rd|th) Gen\b|\b(?:Intel|AMD)\b",
    re.IGNORECASE,
)


def short_cpu_name(raw: str) -> str:
    """ "AMD Ryzen 5 7500F 6-Core Processor" -> "Ryzen 5 7500F"."""
    name = " ".join(_CPU_NOISE.sub(" ", raw).split())
    return name or raw.strip()


def short_gpu_name(raw: str) -> str:
    """ "NVIDIA GeForce RTX 5060" -> "RTX 5060"."""
    name = re.sub(r"\b(NVIDIA|GeForce|Laptop GPU)\b", " ", raw, flags=re.IGNORECASE)
    return " ".join(name.split()) or raw.strip()
