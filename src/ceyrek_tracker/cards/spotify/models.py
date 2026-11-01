"""Spotify kartının veri modelleri: çalan şarkı, ses düzeyi ve çıkış cihazları."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Repeat(Enum):
    OFF = "off"
    LIST = "list"  # çalma listesini / albümü tekrarla
    TRACK = "track"  # şarkıyı tekrarla

    def next(self) -> Repeat:
        """Spotify'daki düğme sırası: kapalı -> liste -> şarkı -> kapalı."""
        order = (Repeat.OFF, Repeat.LIST, Repeat.TRACK)
        return order[(order.index(self) + 1) % len(order)]


@dataclass(frozen=True)
class Track:
    title: str
    artist: str
    album: str


@dataclass(frozen=True)
class NowPlaying:
    """Spotify oturumunun bir andaki görüntüsü.

    `position`, `taken_at` anındaki konumdur (saniye). Spotify konumu 2-4 sn'de bir bildirir;
    çalarken arada geçen süre `position_at` ile eklenerek çubuk akıcı ilerletilir.
    """

    track: Track
    playing: bool
    position: float
    duration: float
    taken_at: float  # time.monotonic()
    shuffle: bool = False
    repeat: Repeat = Repeat.OFF
    # Spotify reklam sırasında şarkı geçmeyi ve atlamayı kapatır.
    can_seek: bool = True
    can_previous: bool = True
    can_next: bool = True
    can_shuffle: bool = True
    can_repeat: bool = True
    cover: bytes | None = None

    def position_at(self, now: float) -> float:
        if not self.playing:
            return self.position
        position = self.position + max(0.0, now - self.taken_at)
        return min(position, self.duration) if self.duration > 0 else position


@dataclass(frozen=True)
class Volume:
    level: float  # 0..1
    muted: bool


@dataclass(frozen=True)
class AudioOutput:
    id: str
    name: str
    is_default: bool


@dataclass(frozen=True)
class Reading:
    """Bir yoklamanın sonucu. `now_playing` None ise Spotify açık değil; `volume` ve `output`,
    Windows'un sistem sesi ve varsayılan çıkış cihazıdır (None ise varsayılan bir çıkış yok)."""

    now_playing: NowPlaying | None
    volume: Volume | None
    output: AudioOutput | None = None
