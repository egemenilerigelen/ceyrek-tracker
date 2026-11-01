"""Kartın Spotify'dan beklediği arayüz.

Gerçek uygulama (`windows.py`) Windows'a özgüdür; kart yalnızca bu arayüzü bilir, bu yüzden
testler sahte bir arka uçla çalışır. Tüm metotlar kartın arka plan thread'inde, sırayla
çağrılır (`worker.py`) ve bloklanabilir; hata durumunda istisna fırlatır.
"""

from __future__ import annotations

from typing import Protocol

from ceyrek_tracker.cards.spotify.models import AudioOutput, Reading, Repeat


class SpotifyBackend(Protocol):
    def prepare(self) -> None:
        """Arka plan thread'i başlarken bir kez çağrılır (ör. COM hazırlığı)."""
        ...

    def read(self) -> Reading: ...

    def set_playing(self, playing: bool) -> None: ...

    def next(self) -> None: ...

    def previous(self) -> None: ...

    def seek(self, seconds: float) -> None: ...

    def set_shuffle(self, enabled: bool) -> None: ...

    def set_repeat(self, mode: Repeat) -> None: ...

    def set_volume(self, level: float) -> None: ...

    def set_muted(self, muted: bool) -> None: ...

    def outputs(self) -> list[AudioOutput]: ...

    def set_output(self, device_id: str) -> None:
        """Windows'un varsayılan ses çıkışını değiştirir (tüm sistemi etkiler)."""
        ...
