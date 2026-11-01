"""Son çalan şarkının diske yazılan kaydı: uygulama Spotify kapalıyken açılsa da kart, telefondaki
gibi en son kalan şarkıyı (kapak ve konumuyla) göstersin."""

from __future__ import annotations

import contextlib
import logging
import os
import time
from pathlib import Path
from typing import Protocol

from ceyrek_tracker.cards.spotify.models import NowPlaying, Track
from ceyrek_tracker.infra import paths
from ceyrek_tracker.infra.storage import read_json, write_json

logger = logging.getLogger(__name__)


def default_path() -> Path:
    return paths.data_dir() / "spotify.json"


def default_cover_path() -> Path:
    return paths.data_dir() / "spotify_cover.bin"


class LastPlayedStore(Protocol):
    """Kartın ihtiyaç duyduğu depo arayüzü; testlerde değiştirilebilir."""

    def load(self) -> NowPlaying | None: ...

    def save(self, now_playing: NowPlaying) -> None: ...


class LastPlayedCache:
    def __init__(self, path: Path | None = None, cover_path: Path | None = None) -> None:
        self.path = path or default_path()
        self.cover_path = cover_path or default_cover_path()
        self._cover_written: bytes | None = None  # değişmeyen kapak her seferinde yazılmasın

    def load(self) -> NowPlaying | None:
        data = read_json(self.path)
        if not isinstance(data, dict):
            return None
        try:
            track = Track(str(data["title"]), str(data["artist"]), str(data["album"]))
            position, duration = float(data["position"]), float(data["duration"])
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("Spotify önbelleği geçersiz: %s", exc)
            return None
        cover = self._read_cover()
        self._cover_written = cover
        return NowPlaying(
            track=track,
            playing=False,
            position=min(max(position, 0.0), duration) if duration > 0 else 0.0,
            duration=max(duration, 0.0),
            taken_at=time.monotonic(),
            cover=cover,
        )

    def save(self, now_playing: NowPlaying) -> None:
        track = now_playing.track
        try:
            write_json(
                self.path,
                {
                    "title": track.title,
                    "artist": track.artist,
                    "album": track.album,
                    "position": now_playing.position,
                    "duration": now_playing.duration,
                },
            )
            self._write_cover(now_playing.cover)
        except OSError as exc:
            logger.warning("Spotify önbelleği yazılamadı: %s", exc)

    def _read_cover(self) -> bytes | None:
        try:
            return self.cover_path.read_bytes() or None
        except OSError:
            return None

    def _write_cover(self, cover: bytes | None) -> None:
        if cover == self._cover_written:
            return
        if cover:
            tmp = self.cover_path.with_name(self.cover_path.name + ".tmp")
            tmp.write_bytes(cover)
            os.replace(tmp, self.cover_path)
        else:
            with contextlib.suppress(FileNotFoundError):
                self.cover_path.unlink()
        self._cover_written = cover
