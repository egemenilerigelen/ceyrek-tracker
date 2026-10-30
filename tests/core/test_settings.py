from ceyrek_tracker.core.settings import CardSetting, Settings, SettingsStore


def test_roundtrip(tmp_path):
    store = SettingsStore(tmp_path / "settings.json")
    original = Settings(
        open_mode="click",
        hover_delay_ms=350,
        pinned=True,
        hotkey="ctrl+alt+p",
        density="relaxed",
        font_scale=1.2,
        accent="#336699",
        cards=(
            CardSetting("weather", enabled=True, collapsed=True, config={"city": "Ankara"}),
            CardSetting("clock", enabled=False),
        ),
    )
    store.save(original)
    assert store.load() == original


def test_missing_and_corrupt_file_give_defaults(tmp_path):
    assert SettingsStore(tmp_path / "yok.json").load() == Settings()
    path = tmp_path / "settings.json"
    path.write_text("{bozuk", encoding="utf-8")
    assert SettingsStore(path).load() == Settings()


def test_invalid_values_are_sanitized():
    s = Settings.from_dict(
        {
            "open_mode": "sürükle",
            "hover_delay_ms": -5,
            "leave_close_seconds": "çok",
            "panel_width": 5000,
            "theme": "mor",
            "density": 3,
            "accent": "kırmızı",
            "font_scale": True,
            "cards": [{"id": "a"}, {"id": "a"}, {"nope": 1}, "x", {"id": "b", "config": 5}],
        }
    )
    d = Settings()
    assert s.open_mode == d.open_mode
    assert s.hover_delay_ms == d.hover_delay_ms
    assert s.leave_close_seconds == d.leave_close_seconds
    assert s.panel_width == d.panel_width
    assert s.theme == d.theme
    assert s.density == d.density
    assert s.accent is None
    assert s.font_scale == d.font_scale
    assert [c.id for c in s.cards] == ["a", "b"]
    assert s.cards[1].config == {}


def test_hotkey_is_normalized_and_may_be_empty():
    assert Settings.from_dict({"hotkey": " Win+Alt+W "}).hotkey == "win+alt+w"
    assert Settings.from_dict({"hotkey": ""}).hotkey == ""


def test_with_card_keeps_order_and_appends_new():
    s = Settings(cards=(CardSetting("a"), CardSetting("b")))
    s = s.with_card(CardSetting("a", collapsed=True)).with_card(CardSetting("c"))
    assert [(c.id, c.collapsed) for c in s.cards] == [("a", True), ("b", False), ("c", False)]
