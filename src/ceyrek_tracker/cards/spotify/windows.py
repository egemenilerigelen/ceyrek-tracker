"""Windows uygulaması: Spotify'ın medya oturumu (GSMTC) ve ses karıştırıcıdaki oturumu (WASAPI).

- Şarkı bilgisi, kapak, konum ve oynat/atla/karıştır/tekrarla komutları Windows'un sistem
  genelindeki medya kontrol katmanından gelir; Spotify hesabına bağlanmak gerekmez.
- Ses düzeyi, Windows'un sistem sesidir (görev çubuğundaki hoparlör). Spotify'ın uygulama
  içi ses çubuğu dışarıdan ayarlanamaz; ses karıştırıcıdaki Spotify satırı ise ne Spotify'da
  ne Windows'un ana çubuğunda görünür bir değişiklik göstermez.
- Çıkış cihazı değişimi Windows'un varsayılan çıkışını değiştirir (tüm sistemi etkiler).

Bu modülü `cards/spotify/__init__.py` kurulurken değil, kart oluşturulurken içe aktarın:
WinRT ya da pycaw yoksa yalnızca bu kart başlatılamaz, panel etkilenmez.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
import warnings
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

import comtypes
from pycaw.api.endpointvolume import IAudioEndpointVolume
from pycaw.constants import DEVICE_STATE, EDataFlow, ERole
from pycaw.pycaw import AudioUtilities
from winrt.windows.media import MediaPlaybackAutoRepeatMode
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSession as Session,
)
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as SessionManager,
)
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionPlaybackStatus as PlaybackStatus,
)
from winrt.windows.storage.streams import Buffer, InputStreamOptions

from ceyrek_tracker.cards.spotify.models import (
    AudioOutput,
    NowPlaying,
    Reading,
    Repeat,
    Track,
    Volume,
)

logger = logging.getLogger(__name__)

TICKS_PER_SECOND = 10_000_000  # WinRT zaman birimi: 100 ns
COVER_SETTLE_READS = 5  # şarkı değişince kapağın okunduğu yoklama sayısı (yaklaşık 5 sn)
# Spotify masaüstü uygulamasının kimliği "Spotify.exe" (Microsoft Store sürümünde
# "SpotifyAB.SpotifyMusic_...").
SPOTIFY = "spotify"

_REPEAT_FROM_WINRT = {
    MediaPlaybackAutoRepeatMode.TRACK: Repeat.TRACK,
    MediaPlaybackAutoRepeatMode.LIST: Repeat.LIST,
}
_REPEAT_TO_WINRT = {
    Repeat.OFF: MediaPlaybackAutoRepeatMode.NONE,
    Repeat.TRACK: MediaPlaybackAutoRepeatMode.TRACK,
    Repeat.LIST: MediaPlaybackAutoRepeatMode.LIST,
}


class WindowsBackend:
    def __init__(self) -> None:
        # Kapak her saniye değil, yalnızca şarkı değişince okunur (yalnızca arka plan thread'i).
        self._cover_track: Track | None = None
        self._cover: bytes | None = None
        self._cover_reads_left = 0
        # Çıkış cihazının adı her saniye değil, cihaz değişince okunur (pahalı bir işlem).
        self._output_id: str | None = None
        self._output_name = ""

    def prepare(self) -> None:
        # WinRT'nin eşzamansız çağrıları sonuçlarını mesaj döngüsüz thread'e ancak çok
        # iş parçacıklı (MTA) bir apartmanda iletebilir.
        comtypes.CoInitializeEx(comtypes.COINIT_MULTITHREADED)

    # --- Okuma --------------------------------------------------------------

    def read(self) -> Reading:
        return Reading(asyncio.run(self._read_media()), self._read_volume(), self._read_output())

    async def _read_media(self) -> NowPlaying | None:
        session = await _find_session()
        if session is None:
            return None
        props = await session.try_get_media_properties_async()
        timeline = session.get_timeline_properties()
        info = session.get_playback_info()
        controls = info.controls
        track = Track(props.title or "", props.artist or "", props.album_title or "")
        playing = info.playback_status == PlaybackStatus.PLAYING
        duration = max(0.0, (timeline.end_time - timeline.start_time).total_seconds())
        position = timeline.position.total_seconds()
        if playing:
            # Spotify konumu seyrek bildirir; bildirimden bu yana geçen süre eklenir.
            position += max(0.0, (datetime.now(UTC) - timeline.last_updated_time).total_seconds())
        if duration > 0:
            position = min(position, duration)
        return NowPlaying(
            track=track,
            playing=playing,
            position=position,
            duration=duration,
            taken_at=time.monotonic(),
            shuffle=bool(info.is_shuffle_active),
            repeat=_REPEAT_FROM_WINRT.get(info.auto_repeat_mode, Repeat.OFF),
            can_seek=controls.is_playback_position_enabled,
            can_previous=controls.is_previous_enabled,
            can_next=controls.is_next_enabled,
            can_shuffle=controls.is_shuffle_enabled,
            can_repeat=controls.is_repeat_enabled,
            cover=await self._cover_of(track, props),
        )

    async def _cover_of(self, track: Track, props: Any) -> bytes | None:
        """Kapak, şarkı değiştikten sonraki birkaç yoklamada okunur, sonra bir daha okunmaz.

        Tek okuma yetmez: Spotify başlığı kapaktan önce güncelleyebilir, ilk okuma boş ya da
        önceki şarkının kapağı olabilir ve o şarkı boyunca yanlış kapak ve renk kalırdı. İçerik
        değişmediyse aynı nesne döner; kart da renkleri boşuna yeniden hesaplamaz.
        """
        if track != self._cover_track:
            self._cover_track = track
            self._cover_reads_left = COVER_SETTLE_READS
        if self._cover_reads_left > 0:
            self._cover_reads_left -= 1
            if props.thumbnail is None:
                if self._cover_reads_left == 0:
                    self._cover = None  # gerçekten kapağı olmayan şarkı
            else:
                with contextlib.suppress(OSError):  # hazır değil: sonraki yoklama yeniden dener
                    data = await _read_stream(props.thumbnail)
                    if data != self._cover:
                        self._cover = data
        return self._cover

    def _read_volume(self) -> Volume | None:
        try:
            endpoint = _endpoint_volume()
            return Volume(endpoint.GetMasterVolumeLevelScalar(), bool(endpoint.GetMute()))
        except comtypes.COMError:
            return None  # varsayılan ses çıkışı yok

    def _read_output(self) -> AudioOutput | None:
        try:
            device_id = _default_endpoint().GetId()
            if device_id != self._output_id:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    name = AudioUtilities.GetSpeakers().FriendlyName
                self._output_id, self._output_name = device_id, name or device_id
        except comtypes.COMError:
            return None  # varsayılan ses çıkışı yok
        return AudioOutput(device_id, self._output_name, True)

    # --- Komutlar -----------------------------------------------------------

    def set_playing(self, playing: bool) -> None:
        self._command(lambda s: s.try_play_async() if playing else s.try_pause_async())

    def next(self) -> None:
        self._command(lambda s: s.try_skip_next_async())

    def previous(self) -> None:
        self._command(lambda s: s.try_skip_previous_async())

    def seek(self, seconds: float) -> None:
        ticks = round(seconds * TICKS_PER_SECOND)
        self._command(lambda s: s.try_change_playback_position_async(ticks))

    def set_shuffle(self, enabled: bool) -> None:
        self._command(lambda s: s.try_change_shuffle_active_async(enabled))

    def set_repeat(self, mode: Repeat) -> None:
        self._command(lambda s: s.try_change_auto_repeat_mode_async(_REPEAT_TO_WINRT[mode]))

    def set_volume(self, level: float) -> None:
        _endpoint_volume().SetMasterVolumeLevelScalar(min(1.0, max(0.0, level)), None)

    def set_muted(self, muted: bool) -> None:
        _endpoint_volume().SetMute(muted, None)

    @staticmethod
    def _command(call: Callable[[Session], Awaitable[bool]]) -> None:
        async def run() -> None:
            session = await _find_session()
            if session is None:
                raise RuntimeError("Spotify açık değil")
            await call(session)

        asyncio.run(run())

    # --- Ses çıkışı ---------------------------------------------------------

    def outputs(self) -> list[AudioOutput]:
        with warnings.catch_warnings():
            # pycaw, bazı cihazların okunamayan özelliklerinde her seferinde uyarı basar.
            warnings.simplefilter("ignore")
            devices = AudioUtilities.GetAllDevices(
                EDataFlow.eRender.value, DEVICE_STATE.ACTIVE.value
            )
            try:
                default_id = AudioUtilities.GetSpeakers().id
            except comtypes.COMError:
                default_id = None
        return [AudioOutput(d.id, d.FriendlyName or d.id, d.id == default_id) for d in devices]

    def set_output(self, device_id: str) -> None:
        # Spotify varsayılan cihazı izler; iletişim rolüne (Teams, Discord) dokunulmaz.
        AudioUtilities.SetDefaultDevice(device_id, [ERole.eConsole, ERole.eMultimedia])


async def _find_session() -> Session | None:
    manager = await SessionManager.request_async()
    for session in manager.get_sessions():
        if SPOTIFY in session.source_app_user_model_id.lower():
            return session
    return None


async def _read_stream(reference: Any) -> bytes:
    stream = await reference.open_read_async()
    try:
        size = int(stream.size)
        buffer = Buffer(size)
        await stream.read_async(buffer, size, InputStreamOptions.NONE)
        return bytes(memoryview(buffer))
    finally:
        stream.close()


def _default_endpoint() -> Any:
    return AudioUtilities.GetDeviceEnumerator().GetDefaultAudioEndpoint(
        EDataFlow.eRender.value, ERole.eMultimedia.value
    )


def _endpoint_volume() -> Any:
    """Varsayılan ses çıkışının ana ses denetimi (görev çubuğundaki hoparlör)."""
    device = _default_endpoint()
    interface = device.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
    # `ctypes.cast` kullanılmaz: sayacı artırmadan ikinci bir işaretçi üretir, ikisi de ayrı
    # ayrı `Release` ettiği için nesne bir kez fazla bırakılır (bellek erişim hatası).
    return interface.QueryInterface(IAudioEndpointVolume)
