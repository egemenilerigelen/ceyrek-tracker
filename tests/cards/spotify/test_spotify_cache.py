import pytest

from ceyrek_tracker.cards.spotify.cache import LastPlayedCache
from ceyrek_tracker.cards.spotify.models import NowPlaying, Track

TRACK = Track("Ara Beni Lütfen", "Kenan Doğulu", "Festival")


@pytest.fixture
def cache(tmp_path):
    return LastPlayedCache(tmp_path / "spotify.json", tmp_path / "cover.bin")


def now_playing(**kwargs):
    base = {
        "track": TRACK,
        "playing": True,
        "position": 83.5,
        "duration": 280.0,
        "taken_at": 5.0,
        "cover": b"kapak",
    }
    return NowPlaying(**{**base, **kwargs})


def test_nothing_saved_yet(cache):
    assert cache.load() is None


def test_roundtrip_restores_track_position_and_cover_as_paused(cache, tmp_path):
    cache.save(now_playing())
    loaded = LastPlayedCache(tmp_path / "spotify.json", tmp_path / "cover.bin").load()
    assert loaded.track == TRACK
    assert loaded.position == 83.5
    assert loaded.duration == 280.0
    assert loaded.cover == b"kapak"
    assert loaded.playing is False  # diskten gelen her zaman duraklatılmış görünür


def test_track_without_cover_is_restored_without_cover(cache):
    cache.save(now_playing(cover=None))
    assert cache.load().cover is None


def test_old_cover_is_removed_when_new_track_has_none(cache, tmp_path):
    cache.save(now_playing())
    assert (tmp_path / "cover.bin").exists()
    cache.save(now_playing(cover=None))
    assert not (tmp_path / "cover.bin").exists()


def test_unchanged_cover_is_not_written_again(cache, tmp_path):
    cache.save(now_playing())
    (tmp_path / "cover.bin").unlink()
    cache.save(now_playing(position=90.0))
    assert not (tmp_path / "cover.bin").exists()  # değişmediği için yeniden yazılmadı


def test_position_is_kept_within_duration(cache):
    cache.save(now_playing(position=999.0))
    assert cache.load().position == 280.0


@pytest.mark.parametrize("content", ["bozuk {", "[1, 2]", '{"title": "x"}', '{"title": 1}'])
def test_corrupt_files_are_ignored(cache, tmp_path, content):
    (tmp_path / "spotify.json").write_text(content, encoding="utf-8")
    assert cache.load() is None


def test_unwritable_location_does_not_raise(tmp_path):
    blocked = tmp_path / "dosya"
    blocked.write_text("x")
    LastPlayedCache(blocked / "alt" / "spotify.json", blocked / "alt" / "c.bin").save(now_playing())
