import pytest

from ceyrek_tracker.cards.spotify.formatting import format_time, summary
from ceyrek_tracker.cards.spotify.models import NowPlaying, Repeat, Track

TRACK = Track("Ara Beni Lütfen", "Kenan Doğulu", "Festival")


@pytest.mark.parametrize(
    ("seconds", "text"),
    [(0, "0:00"), (5.9, "0:05"), (73, "1:13"), (600, "10:00"), (3725, "1:02:05"), (-4, "0:00")],
)
def test_format_time(seconds, text):
    assert format_time(seconds) == text


def test_summary_joins_artist_and_title():
    assert summary("Kenan Doğulu", "Ara Beni Lütfen") == "Kenan Doğulu – Ara Beni Lütfen"
    assert summary("", "Yalnızca şarkı") == "Yalnızca şarkı"
    assert summary("", "") == ""


def test_summary_is_shortened_with_ellipsis():
    text = summary("Çok Uzun Bir Sanatçı Adı", "Bu şarkının adı da oldukça uzun", limit=30)
    assert len(text) == 30
    assert text.endswith("…")


def test_repeat_cycles_like_spotify_button():
    assert Repeat.OFF.next() is Repeat.LIST
    assert Repeat.LIST.next() is Repeat.TRACK
    assert Repeat.TRACK.next() is Repeat.OFF


def _playing(**kwargs):
    base = {"track": TRACK, "playing": True, "position": 80.0, "duration": 200.0, "taken_at": 10.0}
    return NowPlaying(**{**base, **kwargs})


def test_position_advances_while_playing():
    assert _playing().position_at(15.0) == 85.0


def test_position_is_frozen_while_paused():
    assert _playing(playing=False).position_at(99.0) == 80.0


def test_position_never_passes_duration():
    assert _playing().position_at(10_000.0) == 200.0


def test_position_with_unknown_duration_keeps_counting():
    assert _playing(duration=0.0).position_at(20.0) == 90.0


def test_clock_going_backwards_does_not_rewind():
    assert _playing().position_at(5.0) == 80.0
