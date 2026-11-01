"""Windows arka ucunun gerçek Spotify'a ihtiyaç duymayan kısımları.

Gerçek okuma/komutlar Spotify'ın açık olmasını gerektirir; onlar elle denenir.
"""

import asyncio
import gc
import sys
from types import SimpleNamespace

import pytest

pytest.importorskip("winrt.windows.media.control")
pytest.importorskip("pycaw.pycaw")

import comtypes

from ceyrek_tracker.cards.spotify import windows
from ceyrek_tracker.cards.spotify.models import Repeat, Track


def test_every_repeat_mode_maps_to_winrt_and_back():
    assert set(windows._REPEAT_TO_WINRT) == set(Repeat)
    for mode, winrt_mode in windows._REPEAT_TO_WINRT.items():
        assert windows._REPEAT_FROM_WINRT.get(winrt_mode, Repeat.OFF) is mode


def test_backend_can_be_created_without_spotify():
    windows.WindowsBackend()


def test_system_volume_pointer_is_released_cleanly(monkeypatch):
    """COM işaretçisi bir kez fazla bırakılırsa `__del__` içinde (yutulan) bellek hatası çıkar."""
    try:
        windows._endpoint_volume()
    except comtypes.COMError:
        pytest.skip("Bu makinede varsayılan bir ses çıkışı yok")
    problems = []
    monkeypatch.setattr(sys, "unraisablehook", problems.append)
    for _ in range(50):
        endpoint = windows._endpoint_volume()
        endpoint.GetMute()
        del endpoint
        gc.collect()
    assert problems == []


def test_default_output_is_named_and_the_name_is_cached():
    backend = windows.WindowsBackend()
    output = backend._read_output()
    if output is None:
        pytest.skip("Bu makinede varsayılan bir ses çıkışı yok")
    assert output.name
    assert output.is_default
    assert backend._read_output() == output


TRACK = Track("Şarkı", "Sanatçı", "Albüm")
OTHER = Track("Sonraki", "Sanatçı", "Albüm")


@pytest.fixture
def covers(monkeypatch):
    """Kapak okumasını taklit eder: `thumbnail` değeri okunacak baytlardır."""
    reads = []

    async def read(reference):
        reads.append(reference)
        if isinstance(reference, Exception):
            raise reference
        return bytes(reference)

    monkeypatch.setattr(windows, "_read_stream", read)
    return reads


def cover_of(backend, track, thumbnail):
    return asyncio.run(backend._cover_of(track, SimpleNamespace(thumbnail=thumbnail)))


def test_cover_that_arrives_after_the_title_is_picked_up(covers):
    backend = windows.WindowsBackend()
    assert cover_of(backend, TRACK, None) is None  # başlık geldi, kapak henüz yok
    assert cover_of(backend, TRACK, b"kapak") == b"kapak"


def test_previous_songs_cover_is_replaced_once_the_new_one_arrives(covers):
    backend = windows.WindowsBackend()
    cover_of(backend, TRACK, b"eski")
    assert cover_of(backend, OTHER, b"eski") == b"eski"  # Spotify henüz eski kapağı veriyor
    assert cover_of(backend, OTHER, b"yeni") == b"yeni"


def test_old_cover_stays_while_waiting_but_a_coverless_song_ends_up_empty(covers):
    backend = windows.WindowsBackend()
    cover_of(backend, TRACK, b"eski")
    for _ in range(windows.COVER_SETTLE_READS - 1):
        assert cover_of(backend, OTHER, None) == b"eski"  # boş kapak titremesi yok
    assert cover_of(backend, OTHER, None) is None


def test_cover_is_not_read_after_it_settled(covers):
    backend = windows.WindowsBackend()
    for _ in range(windows.COVER_SETTLE_READS + 20):
        cover_of(backend, TRACK, b"kapak")
    assert len(covers) == windows.COVER_SETTLE_READS


def test_unchanged_cover_keeps_the_same_object_so_colours_are_not_recomputed(covers):
    backend = windows.WindowsBackend()
    first = cover_of(backend, TRACK, b"kapak")
    assert cover_of(backend, TRACK, b"kapak") is first


def test_failed_read_is_retried_on_the_next_poll(covers):
    backend = windows.WindowsBackend()
    assert cover_of(backend, TRACK, OSError("hazır değil")) is None
    assert cover_of(backend, TRACK, b"kapak") == b"kapak"
