import pytest
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QPoint
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QMenu

from ceyrek_tracker.cards import CARDS
from ceyrek_tracker.cards.spotify import SPEC, SpotifyCard
from ceyrek_tracker.cards.spotify import card as card_module
from ceyrek_tracker.cards.spotify.models import (
    AudioOutput,
    NowPlaying,
    Reading,
    Repeat,
    Track,
    Volume,
)
from ceyrek_tracker.core.card_base import CardContext
from ceyrek_tracker.core.card_host import CardHost
from ceyrek_tracker.theme import resolve_look

LOOK = resolve_look("dark", "normal", 1.0)
TRACK = Track("Ara Beni Lütfen", "Kenan Doğulu", "Festival")
DEFAULT_VOLUME = Volume(0.7, False)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class FakeStore:
    def __init__(self, loaded=None):
        self.loaded = loaded
        self.saved = []

    def load(self):
        return self.loaded

    def save(self, now_playing):
        self.saved.append(now_playing)


class FakeBackend:
    def __init__(self):
        self.reading = Reading(None, None)
        self.fail_read = False
        self.outputs_list = [
            AudioOutput("a", "Hoparlör", True),
            AudioOutput("b", "Kulaklık", False),
        ]
        self.calls = []

    def prepare(self):
        pass

    def read(self):
        self.calls.append(("read",))
        if self.fail_read:
            raise OSError("bozuk")
        return self.reading

    def set_playing(self, playing):
        self.calls.append(("playing", playing))

    def next(self):
        self.calls.append(("next",))

    def previous(self):
        self.calls.append(("previous",))

    def seek(self, seconds):
        self.calls.append(("seek", seconds))

    def set_shuffle(self, enabled):
        self.calls.append(("shuffle", enabled))

    def set_repeat(self, mode):
        self.calls.append(("repeat", mode))

    def set_volume(self, level):
        self.calls.append(("volume", level))

    def set_muted(self, muted):
        self.calls.append(("muted", muted))

    def outputs(self):
        return self.outputs_list

    def set_output(self, device_id):
        self.calls.append(("output", device_id))


def playing_track(clock, **kwargs):
    base = {
        "track": TRACK,
        "playing": True,
        "position": 83.0,
        "duration": 280.0,
        "taken_at": clock.now,
        "shuffle": True,
        "repeat": Repeat.LIST,
    }
    return NowPlaying(**{**base, **kwargs})


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def backend():
    return FakeBackend()


@pytest.fixture
def store():
    return FakeStore()


@pytest.fixture
def card(qtbot, clock, backend, store):
    card = SpotifyCard(CardContext(LOOK, {}), backend, clock, store)
    qtbot.addWidget(card)
    yield card
    card.shutdown()


@pytest.fixture
def wait_call(qtbot, backend):
    def wait(name, *args):
        qtbot.waitUntil(lambda: (name, *args) in backend.calls, timeout=2000)

    return wait


def go_live(card, clock, volume=DEFAULT_VOLUME, **kwargs):
    card._apply(Reading(playing_track(clock, **kwargs), volume))


def test_registered(qtbot):
    assert SPEC.id == "spotify"
    assert SPEC in CARDS
    assert SPEC.title == "Spotify"


def test_placeholder_before_spotify_was_ever_seen(card):
    assert card._title.full_text() == "Spotify açık değil"
    for button in (card._play, card._previous, card._next, card._shuffle, card._repeat):
        assert not button.isEnabled()
    assert not card._seek.isEnabled()
    assert not card._volume_slider.isEnabled()
    assert card._output.isEnabled()  # çıkış cihazı Spotify'dan bağımsızdır


def test_shows_track_details(card, clock):
    go_live(card, clock)
    assert card._title.full_text() == "Ara Beni Lütfen"
    assert card._artist.full_text() == "Kenan Doğulu"
    assert card._total.text() == "4:40"
    assert card._volume_slider.value() == 70


def test_controls_reflect_playback_state(card, clock):
    go_live(card, clock)
    assert card._play.text() == card_module.PAUSE
    assert card._play.property("playing") is True  # çalarken içi boş
    assert card._shuffle.property("active") is True
    assert card._repeat.property("active") is True
    assert card._repeat.text() == card_module.REPEAT_LIST
    go_live(card, clock, playing=False, shuffle=False, repeat=Repeat.TRACK)
    assert card._play.text() == card_module.PLAY
    assert card._play.property("playing") is False  # duraklayınca dolu
    assert card._shuffle.property("active") is False
    assert card._repeat.text() == card_module.REPEAT_TRACK
    assert card._repeat.property("active") is True


def test_ad_disables_skip_and_seek(card, clock):
    go_live(card, clock, can_next=False, can_previous=False, can_seek=False)
    assert card._play.isEnabled()
    assert not card._next.isEnabled()
    assert not card._previous.isEnabled()
    assert not card._seek.isEnabled()


def test_progress_advances_while_playing_and_freezes_when_paused(card, clock):
    go_live(card, clock)
    assert card._elapsed.text() == "1:23"
    clock.now += 10
    card._render_progress()
    assert card._elapsed.text() == "1:33"
    assert card._seek.value() == 930
    go_live(card, clock, playing=False, position=100.0)
    clock.now += 10
    card._render_progress()
    assert card._elapsed.text() == "1:40"


def test_last_track_stays_when_spotify_closes(card, clock):
    go_live(card, clock)
    card._apply(Reading(None, None))
    assert card._title.full_text() == "Ara Beni Lütfen"
    assert card._play.text() == card_module.PLAY
    assert not card._play.isEnabled()
    assert not card._seek.isEnabled()
    assert not card._volume_slider.isEnabled()
    clock.now += 30
    card._render_progress()
    assert card._elapsed.text() == "1:23"  # kapalıyken ilerlemez


def test_reopening_spotify_enables_controls_again(card, clock):
    go_live(card, clock)
    card._apply(Reading(None, None))
    go_live(card, clock, playing=False)
    assert card._play.isEnabled()
    assert card._volume_slider.isEnabled()


def test_controls_do_nothing_while_spotify_is_closed(card, clock, backend, qtbot):
    go_live(card, clock)
    card._apply(Reading(None, None))
    for action in (
        card._toggle_playing,
        card._skip_next,
        card._skip_previous,
        card._toggle_shuffle,
    ):
        action()
    card._on_seek(100)
    qtbot.wait(50)
    assert backend.calls == []


def test_play_pause_acts_immediately_and_sends_command(card, clock, wait_call):
    go_live(card, clock)
    clock.now += 10
    card._toggle_playing()
    assert card._play.text() == card_module.PLAY  # Spotify'ı beklemeden
    assert card._np.position == 93.0  # durunca konum dondurulur
    wait_call("playing", False)


def test_stale_reading_does_not_undo_a_fresh_command(card, clock):
    go_live(card, clock)
    card._toggle_playing()
    go_live(card, clock)  # Spotify henüz eski durumu bildiriyor
    assert card._play.text() == card_module.PLAY
    clock.now += card_module.HOLD_SECONDS + 0.1
    go_live(card, clock)  # süre doldu: Spotify'ın dediği geçerli
    assert card._play.text() == card_module.PAUSE


def test_old_command_does_not_leak_into_a_later_one(card, clock):
    go_live(card, clock)
    card._toggle_playing()
    clock.now += 10
    go_live(card, clock, playing=True, shuffle=False)
    card._toggle_shuffle()
    # Oynat/duraklat komutunun süresi dolmuştu; ikinci komut onu geri getirmemeli.
    assert card._np.playing is True
    assert card._np.shuffle is True


def test_skip_buttons_send_commands(card, clock, wait_call):
    go_live(card, clock)
    card._next.click()
    card._previous.click()
    wait_call("next")
    wait_call("previous")


def test_shuffle_and_repeat_buttons(card, clock, wait_call):
    go_live(card, clock, shuffle=False, repeat=Repeat.OFF)
    card._shuffle.click()
    wait_call("shuffle", True)
    assert card._shuffle.property("active") is True
    card._repeat.click()
    wait_call("repeat", Repeat.LIST)
    assert card._repeat.property("active") is True


def test_seek_commit_jumps_and_updates_position(card, clock, wait_call):
    go_live(card, clock)
    card._seek.committed.emit(600)
    wait_call("seek", 60.0)
    assert card._np.position == 60.0
    assert card._elapsed.text() == "1:00"


def test_dragging_the_seek_bar_is_not_overwritten_by_progress(card, clock):
    go_live(card, clock)
    card._seek.setSliderDown(True)
    card._seek.setValue(1000)
    assert card._elapsed.text() == "1:40"
    clock.now += 5
    card._render_progress()
    assert card._seek.value() == 1000
    assert card._elapsed.text() == "1:40"


def test_volume_slider_sends_debounced_level(card, clock, qtbot, wait_call, backend):
    go_live(card, clock)
    card._volume_slider.setValue(30)
    card._volume_slider.setValue(35)
    wait_call("volume", 0.35)
    assert [c for c in backend.calls if c[0] == "volume"] == [("volume", 0.35)]
    assert ("muted", False) not in backend.calls


def test_moving_volume_while_muted_unmutes(card, clock, wait_call, backend):
    go_live(card, clock, volume=Volume(0.5, True))
    card._volume_slider.setValue(40)
    wait_call("volume", 0.4)
    assert backend.calls.index(("muted", False)) < backend.calls.index(("volume", 0.4))


def test_volume_reading_does_not_fight_the_user(card, clock):
    go_live(card, clock)
    card._volume_slider.setValue(30)
    go_live(card, clock, volume=Volume(1.0, False))  # eski değer geç geliyor
    assert card._volume_slider.value() == 30
    clock.now += card_module.VOLUME_HOLD_SECONDS + 0.1
    go_live(card, clock, volume=Volume(0.9, False))
    assert card._volume_slider.value() == 90


def test_mute_button_toggles(card, clock, wait_call):
    go_live(card, clock)
    assert card._mute.text() == card_module.VOLUME
    card._mute.click()
    wait_call("muted", True)
    assert card._mute.text() == card_module.MUTED
    card._mute.click()
    wait_call("muted", False)
    assert card._mute.text() == card_module.VOLUME


def test_zero_volume_shows_muted_icon(card, clock):
    go_live(card, clock, volume=Volume(0.0, False))
    assert card._mute.text() == card_module.MUTED


def test_output_menu_lists_devices_and_switches(card, qtbot, wait_call):
    card._output.clicked.emit()
    qtbot.waitUntil(lambda: card._outputs_menu is not None, timeout=2000)
    menu = card._outputs_menu
    actions = menu.actions()
    assert [a.text() for a in actions] == ["Hoparlör", "Kulaklık"]
    assert [a.isChecked() for a in actions] == [True, False]
    actions[1].trigger()
    wait_call("output", "b")
    assert "Kulaklık" in card._output.toolTip()
    menu.close()


def test_output_menu_without_devices(card, backend, qtbot):
    backend.outputs_list = []
    card._output.clicked.emit()
    qtbot.waitUntil(lambda: card._outputs_menu is not None, timeout=2000)
    actions = card._outputs_menu.actions()
    assert len(actions) == 1
    assert not actions[0].isEnabled()
    card._outputs_menu.close()


def test_polling_starts_when_shown_and_stops_when_hidden(card, clock, backend, qtbot):
    backend.reading = Reading(playing_track(clock), Volume(0.7, False))
    card.on_show()
    qtbot.waitUntil(lambda: card._live, timeout=2000)
    assert card._poll_timer.isActive()
    assert card._tick_timer.isActive()  # çalıyor: çubuk akıyor
    card.on_hide()
    assert not card._poll_timer.isActive()
    assert not card._tick_timer.isActive()
    reads = backend.calls.count(("read",))
    card._poll()
    qtbot.wait(50)
    assert backend.calls.count(("read",)) == reads


def test_tick_timer_stops_when_paused(card, clock):
    card.on_show()
    go_live(card, clock)
    assert card._tick_timer.isActive()
    go_live(card, clock, playing=False)
    assert not card._tick_timer.isActive()


def test_read_failure_shows_error_and_clears_on_recovery(card, clock, backend, qtbot):
    backend.fail_read = True
    card.on_show()
    qtbot.waitUntil(lambda: card.current_error != "", timeout=2000)
    backend.fail_read = False
    backend.reading = Reading(playing_track(clock), Volume(0.7, False))
    card._poll()
    qtbot.waitUntil(lambda: card.current_error == "", timeout=2000)
    assert card._live


def test_collapsed_card_summarises_track_in_header(card, clock):
    go_live(card, clock)
    assert card.current_info == ""
    card.on_collapsed(True)
    assert card.current_info == "Kenan Doğulu – Ara Beni Lütfen"
    go_live(card, clock, track=Track("Yeni", "Biri", "A"))
    assert card.current_info == "Biri – Yeni"
    card.on_collapsed(False)
    assert card.current_info == ""


def test_collapsed_summary_in_real_host(qtbot, clock, backend, store):
    card = SpotifyCard(CardContext(LOOK, {}), backend, clock, store)
    host = CardHost(SPEC, card, LOOK, collapsed=True, animate=False)
    qtbot.addWidget(host)
    go_live(card, clock)
    assert host._info.text() == "Kenan Doğulu – Ara Beni Lütfen"
    host.toggle()
    assert host._info.text() == ""
    card.shutdown()


def cached(**kwargs):
    base = {
        "track": TRACK,
        "playing": False,
        "position": 120.0,
        "duration": 280.0,
        "taken_at": 0.0,
    }
    return NowPlaying(**{**base, **kwargs})


def test_last_track_from_disk_is_shown_while_spotify_is_closed(qtbot, clock, backend):
    card = SpotifyCard(CardContext(LOOK, {}), backend, clock, FakeStore(cached()))
    qtbot.addWidget(card)
    assert card._title.full_text() == "Ara Beni Lütfen"
    assert card._elapsed.text() == "2:00"
    assert card._total.text() == "4:40"
    assert not card._play.isEnabled()
    card._apply(Reading(None, None))  # Spotify hâlâ kapalı: kayıt silinmez
    assert card._title.full_text() == "Ara Beni Lütfen"
    card.shutdown()


def test_collapsed_summary_uses_last_track_from_disk(qtbot, clock, backend):
    card = SpotifyCard(CardContext(LOOK, {}), backend, clock, FakeStore(cached()))
    qtbot.addWidget(card)
    card.on_collapsed(True)
    assert card.current_info == "Kenan Doğulu – Ara Beni Lütfen"
    card.shutdown()


def test_spotify_going_live_takes_over_from_the_record(card, clock):
    go_live(card, clock)
    assert card._play.isEnabled()
    assert card._title.full_text() == "Ara Beni Lütfen"


def test_same_track_as_on_disk_is_not_rewritten(qtbot, clock, backend):
    store = FakeStore(cached())
    card = SpotifyCard(CardContext(LOOK, {}), backend, clock, store)
    qtbot.addWidget(card)
    go_live(card, clock)
    assert store.saved == []
    card.shutdown()


def test_track_is_saved_when_it_changes_not_every_second(card, clock, store):
    go_live(card, clock)
    assert len(store.saved) == 1
    clock.now += 5
    go_live(card, clock)
    assert len(store.saved) == 1
    go_live(card, clock, track=Track("Yeni", "Biri", "A"))
    assert len(store.saved) == 2
    assert store.saved[-1].track.title == "Yeni"


def test_late_arriving_cover_is_saved_too(card, clock, store):
    go_live(card, clock)
    go_live(card, clock, cover=b"kapak")
    assert store.saved[-1].cover == b"kapak"


def test_position_is_saved_when_spotify_closes(card, clock, store):
    go_live(card, clock)
    clock.now += 20
    card._apply(Reading(None, None))
    assert store.saved[-1].position == 103.0  # 83 + geçen 20 sn
    clock.now += 60
    card._apply(Reading(None, None))
    assert len(store.saved) == 2  # zaten kapalı: tekrar yazılmaz


def test_position_is_saved_when_panel_hides_and_app_quits(card, clock, store):
    go_live(card, clock)
    clock.now += 10
    card.on_hide()
    assert store.saved[-1].position == 93.0
    clock.now += 10
    card.shutdown()
    assert store.saved[-1].position == 103.0


def test_nothing_is_saved_when_spotify_was_never_seen(card, store):
    card.on_hide()
    card.shutdown()
    assert store.saved == []


def test_volume_follows_system_even_when_spotify_is_closed(card):
    card._apply(Reading(None, Volume(0.4, False)))
    assert card._volume_slider.isEnabled()
    assert card._volume_slider.value() == 40
    assert not card._play.isEnabled()


def test_output_button_names_the_selected_device_in_its_tooltip(card):
    assert card._output.toolTip() == "Ses çıkışı"  # henüz bilinmiyor
    card._apply(Reading(None, None, AudioOutput("a", "Hoparlör (Realtek)", True)))
    assert "Hoparlör (Realtek)" in card._output.toolTip()


def test_choosing_a_device_updates_it_at_once_and_holds_against_stale_reads(
    card, clock, qtbot, wait_call
):
    card._apply(Reading(None, None, AudioOutput("a", "Hoparlör", True)))
    card._output.clicked.emit()
    qtbot.waitUntil(lambda: card._outputs_menu is not None, timeout=2000)
    card._outputs_menu.actions()[1].trigger()
    assert "Kulaklık" in card._output.toolTip()
    card._apply(Reading(None, None, AudioOutput("a", "Hoparlör", True)))  # eski bilgi geç geliyor
    assert "Kulaklık" in card._output.toolTip()
    clock.now += card_module.HOLD_SECONDS + 0.1
    card._apply(Reading(None, None, AudioOutput("b", "Kulaklık", True)))
    assert "Kulaklık" in card._output.toolTip()
    wait_call("output", "b")
    card._outputs_menu.close()


def test_controls_row_holds_only_buttons_and_play_is_centred(qtbot, card):
    card.resize(276, 140)
    card.show()
    qtbot.wait(20)

    def centre(widget):
        return widget.mapTo(card, widget.rect().center())

    assert abs(centre(card._play).x() - card.width() / 2) <= 2
    # Ses ve cihaz kutucuğu, düğmelerin altındaki ayrı satırda.
    assert centre(card._mute).y() > centre(card._play).y()
    assert centre(card._output).y() > centre(card._play).y()
    assert centre(card._seek).y() < centre(card._play).y()


def test_volume_row_is_a_longer_symmetric_bar_between_two_icons(qtbot, card):
    card.resize(276, 140)
    card.show()
    qtbot.wait(20)

    def left(widget):
        return widget.mapTo(card, widget.rect().topLeft()).x()

    def right(widget):
        return left(widget) + widget.width()

    assert card._volume_slider.width() > card._seek.width()  # ses çubuğu daha uzun
    assert left(card._volume_slider) < left(card._seek)
    assert right(card._volume_slider) > right(card._seek)
    # İki yan simge aynı genişlikte ve kartın iki kenarından eşit uzaklıkta.
    assert card._mute.width() == card._output.width()
    assert abs(left(card._mute) - (card.width() - right(card._output))) <= 1
    assert left(card._mute) < left(card._volume_slider) < right(card._volume_slider)
    assert right(card._volume_slider) < left(card._output)


def test_output_button_is_narrower_than_the_time_columns(card):
    assert card._output.width() < card._elapsed.width()


def test_output_menu_opens_to_the_lower_left_of_the_icon(card, qtbot, monkeypatch):
    card.resize(276, 140)
    card.show()
    qtbot.wait(20)
    seen = []
    monkeypatch.setattr(QMenu, "popup", lambda self, pos, action=None: seen.append((self, pos)))
    card._output.clicked.emit()
    qtbot.waitUntil(lambda: bool(seen), timeout=2000)
    menu, pos = seen[0]
    corner = card._output.mapToGlobal(QPoint(card._output.width(), card._output.height()))
    assert pos.y() == corner.y()  # simgenin hemen altında
    assert pos.x() + menu.sizeHint().width() == corner.x()  # sağ kenarı simgeyle hizalı


def test_wide_output_menu_is_kept_inside_the_card(card, qtbot, monkeypatch, backend):
    backend.outputs_list = [AudioOutput("a", "Çok uzun bir cihaz adı " * 12, True)]
    card.resize(276, 140)
    card.show()
    qtbot.wait(20)
    seen = []
    monkeypatch.setattr(QMenu, "popup", lambda self, pos, action=None: seen.append((self, pos)))
    card._output.clicked.emit()
    qtbot.waitUntil(lambda: bool(seen), timeout=2000)
    assert seen[0][1].x() == card.mapToGlobal(QPoint(0, 0)).x()  # sol kenara hizalandı


def _cover(color: str) -> bytes:
    image = QImage(30, 30, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


def test_backdrop_takes_the_tone_of_the_cover_and_returns_to_default_without_one(card, clock):
    from ceyrek_tracker.cards.spotify.palette import DEFAULT

    assert card._backdrop._palette == DEFAULT
    go_live(card, clock, cover=_cover("#2050e0"))
    tone = QColor(card._backdrop._palette.primary).getHslF()[0] * 360
    assert abs(tone - QColor("#2050e0").getHslF()[0] * 360) <= 14
    go_live(card, clock, track=Track("Yeni", "Biri", "A"), cover=None)
    assert card._backdrop._palette == DEFAULT


def test_backdrop_colour_is_only_recomputed_when_the_cover_changes(card, clock, monkeypatch):
    calls = []
    real = card_module.extract_palette
    monkeypatch.setattr(card_module, "extract_palette", lambda data: calls.append(1) or real(data))
    cover = _cover("#30b050")
    go_live(card, clock, cover=cover)
    go_live(card, clock, cover=cover)
    go_live(card, clock, cover=cover)
    assert len(calls) == 1


def test_progress_bar_active_buttons_and_play_fill_take_the_song_colour(card, clock):
    import re

    assert card.styleSheet() == ""  # kapak yok: tema vurgusu (altın) kalır
    go_live(card, clock, cover=_cover("#2050e0"))
    sheet = card.styleSheet()
    for selector in ('QSlider[role="seek"]', '[active="true"]', '[playing="false"]'):
        assert selector in sheet
    tone = re.search(r"#[0-9a-f]{6}", sheet).group(0)
    assert abs(QColor(tone).getHslF()[0] * 360 - QColor("#2050e0").getHslF()[0] * 360) <= 20
    go_live(card, clock, track=Track("Yeni", "Biri", "A"), cover=None)
    assert card.styleSheet() == ""


def test_song_colour_follows_a_theme_change(card, clock):
    go_live(card, clock, cover=_cover("#2050e0"))
    dark_sheet = card.styleSheet()
    card.set_look(resolve_look("light", "normal", 1.0))
    assert card.styleSheet() not in ("", dark_sheet)


def test_corrected_cover_is_saved_too(card, clock, store):
    go_live(card, clock, cover=b"eski kapak")
    go_live(card, clock, cover=b"dogru kapak")
    assert store.saved[-1].cover == b"dogru kapak"
