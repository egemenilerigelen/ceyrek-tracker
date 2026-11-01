"""Spotify kartı: çalan şarkı, kapak, ilerleme çubuğu, kontrol düğmeleri, ses ve çıkış cihazı.

Veri Windows'un medya oturumundan gelir (Spotify hesabına bağlanılmaz). Kart, panel açıkken
saniyede bir okur; çalarken ilerleme çubuğunu aradaki sürede kendisi akıtır. Spotify kapanınca
son şarkı görünür kalır, düğmeler pasifleşir.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import replace
from typing import Any

from PySide6.QtCore import QPoint, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QActionGroup
from PySide6.QtWidgets import QHBoxLayout, QMenu, QToolButton, QVBoxLayout

from ceyrek_tracker.cards.spotify.backdrop import SpotifyBackdrop
from ceyrek_tracker.cards.spotify.backend import SpotifyBackend
from ceyrek_tracker.cards.spotify.cache import LastPlayedCache, LastPlayedStore
from ceyrek_tracker.cards.spotify.formatting import format_time, summary
from ceyrek_tracker.cards.spotify.logo import SpotifyLogo
from ceyrek_tracker.cards.spotify.models import (
    AudioOutput,
    NowPlaying,
    Reading,
    Repeat,
    Volume,
)
from ceyrek_tracker.cards.spotify.palette import DEFAULT, accent_for, extract_palette
from ceyrek_tracker.cards.spotify.widgets import CoverView, ElidedLabel, JumpSlider
from ceyrek_tracker.cards.spotify.worker import Worker
from ceyrek_tracker.core.card_base import Card, CardContext, CardSpec, guarded
from ceyrek_tracker.core.widgets import make_label, repolish
from ceyrek_tracker.theme import Look
from ceyrek_tracker.theme.tokens import rgba

POLL_MS = 1000
TICK_MS = 250  # çalarken ilerleme çubuğunun ve süre yazısının yenilenme aralığı
# Bir komuttan sonra Spotify'ın yeni durumu bildirmesi biraz sürer; bu sürede okumadan gelen
# eski durum, kullanıcının az önce yaptığı değişikliği geri almasın.
HOLD_SECONDS = 1.2
VOLUME_HOLD_SECONDS = 1.5
RECHECK_MS = 350  # komuttan sonra gerçek durumu yeniden oku
VOLUME_DEBOUNCE_MS = 40
SEEK_STEPS = 10  # ilerleme çubuğunun çözünürlüğü: saniyede 10 adım
COVER_SIZE = 48
TIME_WIDTH = 32  # süre yazılarının genişliği (mantıksal px)
ICON_WIDTH = 24  # alt satırdaki simge düğmelerinin genişliği

# Segoe MDL2 Assets karakterleri
PLAY, PAUSE = "", ""
PREVIOUS, NEXT = "", ""
SHUFFLE, REPEAT_LIST, REPEAT_TRACK = "", "", ""
VOLUME, MUTED, OUTPUT = "", "", ""


def accent_stylesheet(accent: str) -> str:
    """Temanın vurgusunu şarkının rengiyle değiştiren kurallar (aynı seçiciler, kart düzeyi)."""
    return f"""
QSlider[role="seek"]::sub-page:horizontal {{ background: {accent}; }}
QToolButton[role="icon"][active="true"] {{ color: {accent}; }}
QToolButton[role="play"][playing="false"] {{ background: {rgba(accent, 0.38)}; }}
QToolButton[role="play"][playing="false"]:hover {{ background: {rgba(accent, 0.5)}; }}
"""


def _tool(glyph: str, tooltip: str, role: str = "icon") -> QToolButton:
    button = QToolButton()
    button.setText(glyph)
    button.setToolTip(tooltip)
    button.setProperty("role", role)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


def _set_flag(button: QToolButton, name: str, value: bool) -> None:
    """Düğmenin stil sayfasında kullanılan dinamik özelliği (`active`, `playing`)."""
    if button.property(name) != value:
        button.setProperty(name, value)
        repolish(button)


def _set_value(slider: JumpSlider, value: int) -> None:
    """Değeri programla değiştirir; kullanıcı değişikliği gibi sinyal yayınlamaz."""
    if slider.value() != value:
        with QSignalBlocker(slider):
            slider.setValue(value)


class SpotifyCard(Card):
    def __init__(
        self,
        context: CardContext,
        backend: SpotifyBackend,
        clock: Callable[[], float] = time.monotonic,
        cache: LastPlayedStore | None = None,
    ) -> None:
        super().__init__(context)
        self._backend = backend
        self._clock = clock
        self._cache = cache or LastPlayedCache()
        # Son bilinen şarkı: Spotify kapanınca da, uygulama Spotify kapalıyken açılınca da kalır.
        self._np: NowPlaying | None = self._cache.load()
        self._saved_key = self._key(self._np)
        self._live = False  # Spotify'ın medya oturumu şu an var mı
        self._volume: Volume | None = None
        self._shown = False
        self._collapsed = False
        self._reading = False
        # Kullanıcının az önce yaptığı, Spotify'ın henüz bildirmediği değişiklikler.
        self._intent: dict[str, Any] = {}
        self._intent_until = 0.0
        self._volume_until = 0.0
        self._output_info: AudioOutput | None = None  # seçili (varsayılan) çıkış cihazı
        self._output_until = 0.0
        self._pending_volume: tuple[float, bool] | None = None  # (düzey, sessizden çıkarılsın mı)
        self._cover_src: bytes | None = None
        self._palette = DEFAULT  # şu anki kapağın renkleri
        self._outputs_menu: QMenu | None = None
        self._build_ui()

        self._worker = Worker(backend.prepare, self)
        self._worker.done.connect(self._on_done, Qt.ConnectionType.QueuedConnection)
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(POLL_MS)
        self._poll_timer.timeout.connect(self._poll)
        self._tick_timer = QTimer(self)
        self._tick_timer.setInterval(TICK_MS)
        self._tick_timer.timeout.connect(self._render_progress)
        self._volume_timer = QTimer(self)
        self._volume_timer.setSingleShot(True)
        self._volume_timer.setInterval(VOLUME_DEBOUNCE_MS)
        self._volume_timer.timeout.connect(self._send_volume)
        self._render()

    # --- Arayüz -------------------------------------------------------------

    def _build_ui(self) -> None:
        look = self.look
        sp = look.metrics.sp
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        # Hava kartındaki gibi çerçeveli kutu; arkasında hafif dalga/daire deseni var.
        self._backdrop = box = SpotifyBackdrop(look)
        outer.addWidget(box)
        rows = QVBoxLayout(box)
        rows.setContentsMargins(sp(10), sp(7), sp(10), sp(5))
        rows.setSpacing(sp(3))

        top = QHBoxLayout()
        top.setSpacing(sp(10))
        self._cover = CoverView(sp(COVER_SIZE), look)
        top.addWidget(self._cover)
        text = QVBoxLayout()
        text.setSpacing(0)
        self._title = ElidedLabel("value")
        self._artist = ElidedLabel("soft")
        text.addStretch()
        text.addWidget(self._title)
        text.addWidget(self._artist)
        text.addStretch()
        top.addLayout(text, 1)
        rows.addLayout(top)

        progress = QHBoxLayout()
        progress.setSpacing(sp(6))
        self._elapsed = make_label("0:00", "dim")
        self._total = make_label("0:00", "dim")
        self._elapsed.setFixedWidth(sp(TIME_WIDTH))
        self._total.setFixedWidth(sp(TIME_WIDTH))
        # Süreler, altındaki simgelerle aynı sütunda ortalanır.
        for label in (self._elapsed, self._total):
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._seek = JumpSlider("seek")
        self._seek.valueChanged.connect(self._on_seek_moved)
        self._seek.committed.connect(self._on_seek)
        progress.addWidget(self._elapsed)
        progress.addWidget(self._seek, 1)
        progress.addWidget(self._total)
        rows.addLayout(progress)

        # Yalnızca düğmeler: oynat kartın tam ortasında.
        controls = QHBoxLayout()
        controls.setSpacing(sp(14))
        self._shuffle = _tool(SHUFFLE, "Karıştır")
        self._previous = _tool(PREVIOUS, "Önceki")
        self._play = _tool(PLAY, "Oynat", role="play")
        self._next = _tool(NEXT, "Sonraki")
        self._repeat = _tool(REPEAT_LIST, "Tekrarla")
        controls.addStretch()
        for button in (self._shuffle, self._previous, self._play, self._next, self._repeat):
            controls.addWidget(button, 0, Qt.AlignmentFlag.AlignVCenter)
        controls.addStretch()
        rows.addLayout(controls)

        # Alt satırın tamamı ses: solda sessize alma, sağda çıkış cihazı simgesi (tıklayınca
        # cihaz listesi açılır; seçili cihazın adı ipucunda). Simgeler dar ve eşit genişlikte:
        # ses çubuğu ilerleme çubuğundan uzun, satır iki yanda simetrik.
        audio = QHBoxLayout()
        audio.setSpacing(sp(4))
        self._mute = _tool(VOLUME, "Sistem sesini kapat")
        self._volume_slider = JumpSlider("volume")
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setMinimumWidth(sp(40))
        self._volume_slider.setToolTip("Sistem sesi")
        self._volume_slider.valueChanged.connect(self._on_volume_moved)
        self._output = _tool(OUTPUT, "Ses çıkışı", role="output")
        for button in (self._mute, self._output):
            button.setFixedWidth(sp(ICON_WIDTH))
        audio.addWidget(self._mute, 0, Qt.AlignmentFlag.AlignVCenter)
        audio.addWidget(self._volume_slider, 1, Qt.AlignmentFlag.AlignVCenter)
        audio.addWidget(self._output, 0, Qt.AlignmentFlag.AlignVCenter)
        rows.addLayout(audio)
        self._shuffle.clicked.connect(self._toggle_shuffle)
        self._previous.clicked.connect(self._skip_previous)
        self._play.clicked.connect(self._toggle_playing)
        self._next.clicked.connect(self._skip_next)
        self._repeat.clicked.connect(self._cycle_repeat)
        self._mute.clicked.connect(self._toggle_mute)
        self._output.clicked.connect(self._request_outputs)

    def set_look(self, look: Look) -> None:
        super().set_look(look)
        self._cover.set_look(look)
        self._backdrop.set_look(look)
        self._apply_accent()

    def _apply_accent(self) -> None:
        """Şarkı çubuğu, aktif düğmeler ve oynat dolgusu kapağın tonunu alır; kapak yoksa
        temanın vurgusu (altın) kalır. Kurallar yalnızca bu kartta geçerlidir."""
        accent = accent_for(self._palette, self.look.theme)
        self.setStyleSheet(accent_stylesheet(accent) if accent else "")

    # --- Yoklama ------------------------------------------------------------

    def _poll(self) -> None:
        if self._reading or not self._shown:
            return
        self._reading = True
        self._worker.submit("read", self._backend.read)

    @guarded
    def _on_done(self, tag: str, value: Any, error: str) -> None:
        if tag == "read":
            self._reading = False
            if error:
                self.fail("Spotify bilgisi okunamıyor")
                return
            if self.current_error:
                self.clear_error()
            self._apply(value)
        elif tag == "outputs":
            if not error:
                self._show_outputs(value)
        else:
            # Komut sonucu: başarılı olsun olmasın gerçek durumu yeniden oku.
            QTimer.singleShot(RECHECK_MS, self._poll)

    def _apply(self, reading: Reading) -> None:
        now = self._clock()
        np = reading.now_playing
        if np is None and self._live:
            self._remember()  # Spotify az önce kapandı: son konum diske yazılsın
        self._live = np is not None
        if np is not None:
            if now < self._intent_until:
                np = replace(np, **self._intent)
            self._np = np
            if self._key(np) != self._saved_key:
                self._remember()
        if now >= self._volume_until:
            self._volume = reading.volume
        if now >= self._output_until:
            self._output_info = reading.output
        self._render()

    # --- Son şarkı ----------------------------------------------------------

    @staticmethod
    def _key(np: NowPlaying | None) -> tuple[Any, ...] | None:
        """Diske yeniden yazmayı gerektiren değişiklikler: şarkı ya da kapağı (geç gelen ya da
        düzelen kapak dahil) değişti mi."""
        return None if np is None else (np.track, np.duration, np.cover)

    def _remember(self) -> None:
        np = self._np
        if np is None:
            return
        position = np.position_at(self._clock()) if self._live else np.position
        self._saved_key = self._key(np)
        self._cache.save(replace(np, position=position))

    # --- Çizim --------------------------------------------------------------

    def _render(self) -> None:
        self._render_track()
        self._render_controls()
        self._render_volume()
        self._render_output()
        self._render_progress()
        self._publish_info()
        self._sync_timers()

    def _render_track(self) -> None:
        np = self._np
        if np is None:
            self._title.set_full_text("Spotify açık değil")
            self._artist.set_full_text("")
        else:
            self._title.set_full_text(np.track.title or "—")
            self._artist.set_full_text(np.track.artist)
        cover = np.cover if np is not None else None
        if cover is not self._cover_src:
            self._cover_src = cover
            self._cover.set_cover(cover)
            self._palette = extract_palette(cover)
            self._backdrop.set_palette(self._palette)  # arka plan kapağın tonunu alır
            self._apply_accent()

    def _render_controls(self) -> None:
        np = self._np
        live = self._live and np is not None
        playing = live and np.playing
        self._play.setText(PAUSE if playing else PLAY)
        _set_flag(self._play, "playing", playing)  # çalarken içi boş, duraklayınca dolu
        self._play.setToolTip("Duraklat" if playing else "Oynat")
        self._play.setEnabled(live)
        self._previous.setEnabled(live and np.can_previous)
        self._next.setEnabled(live and np.can_next)
        self._shuffle.setEnabled(live and np.can_shuffle)
        _set_flag(self._shuffle, "active", live and np.shuffle)
        repeat = np.repeat if live else Repeat.OFF
        self._repeat.setEnabled(live and np.can_repeat)
        self._repeat.setText(REPEAT_TRACK if repeat is Repeat.TRACK else REPEAT_LIST)
        _set_flag(self._repeat, "active", repeat is not Repeat.OFF)

    def _render_volume(self) -> None:
        volume = self._volume
        self._volume_slider.setEnabled(volume is not None)
        self._mute.setEnabled(volume is not None)
        if volume is None:
            return
        if not self._volume_slider.isSliderDown():
            _set_value(self._volume_slider, round(volume.level * 100))
        silent = volume.muted or volume.level == 0
        self._mute.setText(MUTED if silent else VOLUME)
        self._mute.setToolTip("Sistem sesini aç" if volume.muted else "Sistem sesini kapat")

    def _render_output(self) -> None:
        output = self._output_info
        self._output.setToolTip(
            f"Ses çıkışı: {output.name}" if output is not None else "Ses çıkışı"
        )

    def _render_progress(self) -> None:
        np = self._np
        if np is None:
            self._elapsed.setText("0:00")
            self._total.setText("0:00")
            self._seek.setEnabled(False)
            _set_value(self._seek, 0)
            return
        position = np.position_at(self._clock()) if self._live else np.position
        steps = round(np.duration * SEEK_STEPS)
        with QSignalBlocker(self._seek):
            self._seek.setRange(0, steps)
        self._seek.setEnabled(self._live and np.can_seek and steps > 0)
        self._total.setText(format_time(np.duration))
        if not self._seek.isSliderDown():  # sürüklerken değeri kullanıcı belirler
            _set_value(self._seek, round(position * SEEK_STEPS))
            self._elapsed.setText(format_time(position))

    def _publish_info(self) -> None:
        np = self._np
        self.set_info(
            summary(np.track.artist, np.track.title) if self._collapsed and np is not None else ""
        )

    def _sync_timers(self) -> None:
        np = self._np
        ticking = self._shown and self._live and np is not None and np.playing
        if ticking and not self._tick_timer.isActive():
            self._tick_timer.start()
        elif not ticking and self._tick_timer.isActive():
            self._tick_timer.stop()

    # --- Komutlar -----------------------------------------------------------

    def _send(self, tag: str, job: Callable[[], Any], **intent: Any) -> None:
        """Komutu arka plana verir ve `intent`teki değişikliği Spotify bildirene kadar
        ekranda tutar (düğme basıldığı anda tepki versin)."""
        now = self._clock()
        if intent and self._np is not None:
            if now >= self._intent_until:
                self._intent = {}
            self._intent.update(intent)
            self._intent_until = now + HOLD_SECONDS
            self._np = replace(self._np, **intent)
            self._render()
        self._worker.submit(tag, job)

    def _controllable(self) -> NowPlaying | None:
        return self._np if self._live else None

    @guarded
    def _toggle_playing(self) -> None:
        np = self._controllable()
        if np is None:
            return
        playing = not np.playing
        now = self._clock()
        self._send(
            "play",
            lambda: self._backend.set_playing(playing),
            playing=playing,
            position=np.position_at(now),  # durunca konum dondurulur, başlayınca oradan akar
            taken_at=now,
        )

    @guarded
    def _skip_next(self) -> None:
        if self._controllable() is not None:
            self._send("next", self._backend.next)

    @guarded
    def _skip_previous(self) -> None:
        if self._controllable() is not None:
            self._send("previous", self._backend.previous)

    @guarded
    def _toggle_shuffle(self) -> None:
        np = self._controllable()
        if np is not None:
            enabled = not np.shuffle
            self._send("shuffle", lambda: self._backend.set_shuffle(enabled), shuffle=enabled)

    @guarded
    def _cycle_repeat(self) -> None:
        np = self._controllable()
        if np is not None:
            mode = np.repeat.next()
            self._send("repeat", lambda: self._backend.set_repeat(mode), repeat=mode)

    def _on_seek_moved(self, value: int) -> None:
        if self._seek.isSliderDown():
            self._elapsed.setText(format_time(value / SEEK_STEPS))

    @guarded
    def _on_seek(self, value: int) -> None:
        if self._controllable() is None:
            return
        seconds = value / SEEK_STEPS
        self._send(
            "seek",
            lambda: self._backend.seek(seconds),
            position=seconds,
            taken_at=self._clock(),
        )

    @guarded
    def _on_volume_moved(self, value: int) -> None:
        volume = self._volume
        if volume is None:
            return
        level = value / 100
        # Sessizdeyken çubuğu oynatmak sesi de açar.
        unmute = volume.muted or (self._pending_volume is not None and self._pending_volume[1])
        self._pending_volume = (level, unmute)
        self._volume = Volume(level, False)
        self._volume_until = self._clock() + VOLUME_HOLD_SECONDS
        self._render_volume()
        self._volume_timer.start()

    @guarded
    def _send_volume(self) -> None:
        if self._pending_volume is None:
            return
        level, unmute = self._pending_volume
        self._pending_volume = None

        def job() -> None:
            if unmute:
                self._backend.set_muted(False)
            self._backend.set_volume(level)

        self._worker.submit("volume", job)

    @guarded
    def _toggle_mute(self) -> None:
        volume = self._volume
        if volume is None:
            return
        muted = not volume.muted
        self._volume = Volume(volume.level, muted)
        self._volume_until = self._clock() + VOLUME_HOLD_SECONDS
        self._render_volume()
        self._worker.submit("mute", lambda: self._backend.set_muted(muted))

    # --- Ses çıkışı ---------------------------------------------------------

    def _request_outputs(self) -> None:
        self._worker.submit("outputs", self._backend.outputs)

    def _show_outputs(self, outputs: list[AudioOutput]) -> None:
        if self._outputs_menu is not None:
            self._outputs_menu.deleteLater()
        menu = self._outputs_menu = QMenu(self)
        group = QActionGroup(menu)
        for output in outputs:
            action = menu.addAction(output.name)
            action.setCheckable(True)
            action.setChecked(output.is_default)
            action.triggered.connect(lambda _checked=False, o=output: self._select_output(o))
            group.addAction(action)
        if not outputs:
            menu.addAction("Çıkış cihazı bulunamadı").setEnabled(False)
        # Simgenin sol aşağısına açılır: menünün sağ üst köşesi simgenin sağ alt köşesinde.
        # Menü kartın sol kenarından taşacak kadar genişse sol kenara hizalanır; böylece
        # panelin dışına çıkıp 'dışarı tıklama' sayılmaz.
        corner = self._output.mapToGlobal(QPoint(self._output.width(), self._output.height()))
        left = self.mapToGlobal(QPoint(0, 0)).x()
        menu.popup(QPoint(max(corner.x() - menu.sizeHint().width(), left), corner.y()))

    @guarded
    def _select_output(self, output: AudioOutput) -> None:
        # Kutucuk hemen yeni cihazı göstersin; Windows'un yeni varsayılanı bildirmesi sürer.
        self._output_info = replace(output, is_default=True)
        self._output_until = self._clock() + HOLD_SECONDS
        self._render_output()
        self._worker.submit("output", lambda: self._backend.set_output(output.id))

    # --- Yaşam döngüsü ------------------------------------------------------

    def on_show(self) -> None:
        self._shown = True
        self._poll()
        self._poll_timer.start()
        self._sync_timers()

    def on_hide(self) -> None:
        self._shown = False
        if self._live:
            self._remember()  # panel kapanınca konum güncellenmez; son konum saklansın
        self._poll_timer.stop()
        self._tick_timer.stop()

    def on_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._publish_info()

    def shutdown(self) -> None:
        if self._live:
            self._remember()
        self._shown = False
        for timer in (self._poll_timer, self._tick_timer, self._volume_timer):
            timer.stop()
        self._worker.stop()


def _create(context: CardContext) -> Card:
    # İçe aktarma burada: WinRT ya da pycaw yüklenemezse yalnızca bu kart başlatılamaz.
    from ceyrek_tracker.cards.spotify.windows import WindowsBackend

    return SpotifyCard(context, WindowsBackend())


SPEC = CardSpec(
    id="spotify", title="Spotify", icon="\ue8d6", factory=_create, icon_factory=SpotifyLogo
)


__all__ = ["SPEC", "SpotifyCard"]
