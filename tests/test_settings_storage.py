from datetime import datetime

from ceyrek_tracker.domain.catalog import GOLD_TYPES
from ceyrek_tracker.domain.models import Quote, Snapshot
from ceyrek_tracker.settings import DEFAULT_REFRESH, Settings, SettingsStore
from ceyrek_tracker.storage import SnapshotCache


def test_settings_roundtrip(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    original = Settings(
        provider="altinkaynak",
        refresh_seconds=120,
        featured="gram",
        visible=("gram", "ceyrek"),
        expanded=True,
        always_on_top=True,
        window_pos=(100, -20),
    )
    store.save(original)
    assert store.load() == original


def test_missing_file_gives_defaults(tmp_path):
    settings = SettingsStore(tmp_path / "yok.json").load()
    assert settings == Settings()
    assert settings.visible == tuple(g.id for g in GOLD_TYPES)


def test_corrupt_file_gives_defaults(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{bozuk", encoding="utf-8")
    assert SettingsStore(path).load() == Settings()


def test_invalid_values_are_sanitized():
    settings = Settings.from_dict(
        {
            "provider": "bilinmeyen-kaynak",
            "refresh_seconds": 5,
            "featured": "platin",
            "visible": ["ceyrek", "ceyrek", "bilinmeyen", 3],
            "window_pos": ["a", 1],
        }
    )
    assert settings.provider == Settings().provider
    assert settings.refresh_seconds == DEFAULT_REFRESH
    assert settings.featured == "ceyrek"
    assert settings.visible == ("ceyrek",)
    assert settings.window_pos is None


def test_bool_is_not_accepted_as_interval():
    assert Settings.from_dict({"refresh_seconds": True}).refresh_seconds == DEFAULT_REFRESH


def test_snapshot_cache_roundtrip(tmp_path):
    cache = SnapshotCache(tmp_path / "snap.json")
    snapshot = Snapshot(
        source_id="truncgil",
        source_name="Truncgil",
        quotes={
            "ceyrek": Quote("ceyrek", 10392.68, 10632.48, 0.0),
            "ons": Quote("ons", 4024.95, 4025.59, None),
        },
        fetched_at=datetime(2026, 10, 29, 16, 41, 5),
        source_time=datetime(2026, 10, 29, 16, 30, 3),
    )
    cache.save(snapshot)
    assert cache.load() == snapshot


def test_snapshot_cache_ignores_invalid(tmp_path):
    path = tmp_path / "snap.json"
    path.write_text('{"source_id": "x"}', encoding="utf-8")
    assert SnapshotCache(path).load() is None
