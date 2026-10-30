"""Kaynaklardan gelen fiyat verisinin taşındığı değişmez veri modelleri."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


@dataclass(frozen=True, slots=True)
class Quote:
    type_id: str
    buy: float
    sell: float
    # Günlük değişim yüzdesi; kaynak vermiyorsa None.
    change_pct: float | None = None


@dataclass(frozen=True, slots=True)
class Snapshot:
    """Tek bir başarılı veri çekiminin sonucu."""

    source_id: str
    source_name: str
    quotes: dict[str, Quote]
    fetched_at: datetime
    # Kaynağın kendi beyan ettiği güncelleme zamanı (İstanbul saati).
    source_time: datetime | None = None

    def get(self, type_id: str) -> Quote | None:
        return self.quotes.get(type_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "fetched_at": self.fetched_at.isoformat(),
            "source_time": self.source_time.isoformat() if self.source_time else None,
            "quotes": {
                q.type_id: {"buy": q.buy, "sell": q.sell, "change_pct": q.change_pct}
                for q in self.quotes.values()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        quotes = {
            type_id: Quote(
                type_id=type_id,
                buy=float(q["buy"]),
                sell=float(q["sell"]),
                change_pct=None if q.get("change_pct") is None else float(q["change_pct"]),
            )
            for type_id, q in data["quotes"].items()
        }
        source_time = data.get("source_time")
        return cls(
            source_id=data["source_id"],
            source_name=data["source_name"],
            quotes=quotes,
            fetched_at=datetime.fromisoformat(data["fetched_at"]),
            source_time=datetime.fromisoformat(source_time) if source_time else None,
        )


class Trend(Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    UNKNOWN = "unknown"


def compare(current: float, previous: float | None) -> Trend:
    if previous is None:
        return Trend.UNKNOWN
    if current > previous:
        return Trend.UP
    if current < previous:
        return Trend.DOWN
    return Trend.FLAT


class FeedStatus(Enum):
    LOADING = "loading"  # Henüz hiç veri yok, ilk istek bekleniyor
    LIVE = "live"  # Son istek başarılı
    STALE = "stale"  # Elde veri var ama güncel değil (hata, uyku vb.)
    OFFLINE = "offline"  # Hiç veri alınamadı


@dataclass(frozen=True, slots=True)
class FeedState:
    status: FeedStatus
    message: str = ""
    last_success: datetime | None = None
    errors: tuple[str, ...] = field(default_factory=tuple)
