"""Süre ve başlık biçimlendirme."""

from __future__ import annotations

ELLIPSIS = "…"


def format_time(seconds: float) -> str:
    """73 -> '1:13', 3725 -> '1:02:05'."""
    total = max(0, int(seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def summary(artist: str, title: str, limit: int = 30) -> str:
    """Katlı kartın başlık satırındaki kısa özet: 'Sanatçı – Şarkı', uzunsa kısaltılır."""
    text = " – ".join(part for part in (artist, title) if part)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + ELLIPSIS
