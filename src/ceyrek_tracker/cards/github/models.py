"""GitHub katkı tablosunun veri modeli."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

MAX_LEVEL = 4  # GitHub'ın yoğunluk basamakları: 0 (katkı yok) .. 4


@dataclass(frozen=True)
class ContributionDay:
    day: date
    count: int
    level: int  # 0..MAX_LEVEL; GitHub'ın kendi renk basamağı


@dataclass(frozen=True)
class Contributions:
    """Tarih sırasındaki son bir yılın katkı günleri."""

    username: str
    days: tuple[ContributionDay, ...]
    fetched_at: datetime

    @property
    def total(self) -> int:
        return sum(d.count for d in self.days)

    def streak(self, today: date) -> int:
        """Bugünde biten ardışık katkılı gün sayısı. Bugün henüz katkı yoksa seri bozulmuş
        sayılmaz, dünden geriye sayılır (GitHub da böyle gösterir)."""
        counts = {d.day: d.count for d in self.days}
        cursor = today if counts.get(today, 0) > 0 else today - timedelta(days=1)
        run = 0
        while counts.get(cursor, 0) > 0:
            run += 1
            cursor -= timedelta(days=1)
        return run

    def to_dict(self) -> dict[str, Any]:
        return {
            "username": self.username,
            "fetched_at": self.fetched_at.isoformat(),
            "days": [[d.day.isoformat(), d.count, d.level] for d in self.days],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Contributions:
        days = tuple(
            ContributionDay(date.fromisoformat(str(day)), int(count), int(level))
            for day, count, level in data["days"]
        )
        return cls(str(data["username"]), days, datetime.fromisoformat(data["fetched_at"]))
