"""Kopyalanan metinlerin kısa geçmişi: yeni olan başa gelir, tekrar edenler tek satır olur."""

from __future__ import annotations

MAX_ITEMS = 5
PREVIEW_CHARS = 200  # satırda gösterilen en fazla karakter; çok uzun metin arayüzü yormasın


class ClipboardHistory:
    def __init__(self, limit: int = MAX_ITEMS) -> None:
        self._limit = limit
        self._items: list[str] = []

    @property
    def items(self) -> tuple[str, ...]:
        """En yeni başta."""
        return tuple(self._items)

    def add(self, text: str) -> bool:
        """Metni başa alır. Liste değiştiyse `True`; boş metin ya da zaten en üstteki metin
        listeyi değiştirmez."""
        if not text.strip() or (self._items and self._items[0] == text):
            return False
        if text in self._items:
            self._items.remove(text)
        self._items.insert(0, text)
        del self._items[self._limit :]
        return True

    def remove(self, text: str) -> bool:
        if text not in self._items:
            return False
        self._items.remove(text)
        return True


def preview(text: str) -> str:
    """Tek satıra indirilmiş önizleme: satır sonları ve girintiler tek boşluk olur."""
    flat = " ".join(text.split())
    return flat if len(flat) <= PREVIEW_CHARS else flat[:PREVIEW_CHARS].rstrip() + "…"
