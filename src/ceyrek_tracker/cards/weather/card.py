"""Hava durumu kartı: anlık durum, nem/rüzgar/yağış kutuları ve 3 günlük tahmin."""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QHBoxLayout, QMenu, QVBoxLayout

from ceyrek_tracker.cards.weather import api
from ceyrek_tracker.cards.weather.backdrop import WeatherBackdrop
from ceyrek_tracker.cards.weather.cache import WeatherCache, WeatherStore
from ceyrek_tracker.cards.weather.icon import WeatherIcon
from ceyrek_tracker.cards.weather.places import DEFAULT_CITY, PLACES
from ceyrek_tracker.core.card_base import Card, CardContext, CardSpec, guarded
from ceyrek_tracker.core.polling import Poller
from ceyrek_tracker.core.turkish import day_name
from ceyrek_tracker.core.widgets import make_frame, make_label
from ceyrek_tracker.infra.http import create_session
from ceyrek_tracker.theme import Look

DEFAULT_REFRESH_MINUTES = 20


def _deg(value: float) -> str:
    return f"{round(value)}°"


def day_label(day, today) -> str:
    if day == today:
        return "Bugün"
    if day == today + timedelta(days=1):
        return "Yarın"
    return day_name(day)


class WeatherCard(Card):
    def __init__(self, context: CardContext, cache: WeatherStore | None = None) -> None:
        super().__init__(context)
        self._city = str(self.config.get("city") or DEFAULT_CITY)
        minutes = self.config.get("refresh_minutes")
        if not isinstance(minutes, int) or isinstance(minutes, bool) or not 5 <= minutes <= 180:
            minutes = DEFAULT_REFRESH_MINUTES
        self._interval = minutes * 60
        self._cache = cache or WeatherCache()
        self._place, self._weather = self._cache.load()
        if self._place is not None and self._place.query != self._city:
            self._place = self._weather = None  # şehir değişmiş, eski veri geçersiz
        self._stale = False
        self._last_ok: datetime | None = self._weather.fetched_at if self._weather else None
        self._session = create_session()
        self._build_ui(self.look)
        self.set_info(self._city)  # veri gelmeden de konum adı görünür, tıklanıp değiştirilebilir

        self._poller = Poller(self._fetch, self._interval, self)
        self._poller.succeeded.connect(self._on_success)
        self._poller.failed.connect(self._on_failure)
        # Hava verisi hafiftir: panel kapalıyken de seyrek (varsayılan 20 dk) güncellenir.
        self._poller.start(immediate=self._weather is None or self._is_old())

        if self._weather is not None:
            # Önbellekteki veri hemen gösterilir; "eski veri" notu ancak güncelleme gerçekten
            # başarısız olursa (_on_failure) çıkar, her açılışta değil.
            self._render(self._weather)
            self._publish_info()

    # --- Arayüz -------------------------------------------------------------

    def _build_ui(self, look: Look) -> None:
        sp, fs = look.metrics.sp, look.metrics.fs
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self._backdrop = WeatherBackdrop(look)
        inner = self._backdrop
        box = QVBoxLayout(inner)
        box.setContentsMargins(sp(8), sp(6), sp(8), sp(6))
        box.setSpacing(sp(4))

        top = QHBoxLayout()
        top.setSpacing(sp(8))
        self._temp = make_label("--°", "big")
        top.addWidget(self._temp)
        text = QVBoxLayout()
        text.setSpacing(0)
        self._desc = make_label("Veri bekleniyor", "value")
        self._feels = make_label("", "soft")
        text.addStretch()
        text.addWidget(self._desc)
        text.addWidget(self._feels)
        text.addStretch()
        top.addLayout(text, 1)
        self.info_menu = self._build_menu()
        self._icon = WeatherIcon(fs(24))
        self._icon.set_colors(look.theme.accent, look.theme.text_soft)
        top.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignVCenter)
        box.addLayout(top)

        tiles = QHBoxLayout()
        tiles.setSpacing(sp(4))
        self._humidity = self._tile(tiles, "Nem", look)
        self._wind = self._tile(tiles, "Rüzgar", look)
        self._rain = self._tile(tiles, "Yağış", look)
        box.addLayout(tiles)

        # Günün bilgileriyle tahmin satırını ince bir çizgi ayırır; aralık daraltıldığı için
        # kart yüksekliği yaklaşık aynı kalır.
        divider = QHBoxLayout()
        divider.setContentsMargins(sp(8), sp(2), sp(8), 0)
        divider.addWidget(make_frame("divider"))
        box.addLayout(divider)

        days = QHBoxLayout()
        days.setSpacing(sp(4))
        self._day_labels: list[tuple] = []
        for _ in range(3):
            icon = WeatherIcon(fs(18))
            icon.set_colors(look.theme.accent, look.theme.text_soft)
            name = make_label("", "dim")
            value = make_label("", "soft")
            text = QVBoxLayout()
            text.setSpacing(0)
            text.addWidget(name)
            text.addWidget(value)
            cell = QHBoxLayout()
            cell.setSpacing(sp(3))
            cell.addStretch(1)
            cell.addWidget(icon)
            cell.addLayout(text)
            cell.addStretch(1)
            days.addLayout(cell, 1)
            self._day_labels.append((name, value, icon))
        box.addLayout(days)
        outer.addWidget(inner)

    def _build_menu(self) -> QMenu:
        menu = QMenu(self)
        group = QActionGroup(menu)
        self._city_actions: dict[str, QAction] = {}
        for name in PLACES:
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(name == self._city)
            action.triggered.connect(lambda _checked=False, n=name: self._select_city(n))
            group.addAction(action)
            self._city_actions[name] = action
        return menu

    @guarded
    def _select_city(self, city: str) -> None:
        if city == self._city:
            return
        self._city = city
        for name, action in self._city_actions.items():
            action.setChecked(name == city)
        self._place = self._weather = None  # eski şehrin verisi yeni başlığın altında kalmasın
        self._last_ok = None
        self._stale = False
        self.clear_error()
        self._reset_view()
        self.set_info(city)
        self.save_config("city", city)
        self._poller.set_fetch(self._fetch)

    def _reset_view(self) -> None:
        self._temp.setText("--°")
        self._desc.setText("Veri bekleniyor")
        self._feels.setText("")
        self._icon.set_kind(api.KIND_CLOUDY)
        self._backdrop.set_kind(api.KIND_CLOUDY)
        for tile in (self._humidity, self._wind, self._rain):
            tile.setText("--")
        for name, value, icon in self._day_labels:
            name.setText("")
            value.setText("")
            icon.set_kind(api.KIND_CLOUDY)

    @staticmethod
    def _tile(parent: QHBoxLayout, title: str, look: Look):
        sp = look.metrics.sp
        tile = make_frame("tile")
        col = QVBoxLayout(tile)
        col.setContentsMargins(sp(6), sp(2), sp(6), sp(2))
        col.setSpacing(0)
        col.addWidget(make_label(title, "dim"))
        value = make_label("--", "value")
        col.addWidget(value)
        parent.addWidget(tile, 1)
        return value

    def set_look(self, look: Look) -> None:
        super().set_look(look)
        self._icon.set_colors(look.theme.accent, look.theme.text_soft)
        self._backdrop.set_look(look)
        for _, _, icon in self._day_labels:
            icon.set_colors(look.theme.accent, look.theme.text_soft)

    # --- Veri ---------------------------------------------------------------

    def _is_old(self) -> bool:
        return self._last_ok is None or datetime.now() - self._last_ok > timedelta(
            seconds=self._interval
        )

    def _fetch(self) -> tuple[api.Place, api.Weather]:
        """Arka plan thread'inde çalışır."""
        city = self._city
        place = self._place
        if place is None or place.query != city:
            place = PLACES.get(city) or api.find_place(self._session, city)
        weather = api.fetch_weather(self._session, place)
        self._cache.save(place, weather)
        return place, weather

    @guarded
    def _on_success(self, result: tuple[api.Place, api.Weather]) -> None:
        self._place, self._weather = result
        self._last_ok = self._weather.fetched_at
        self._stale = False
        self.clear_error()
        self._render(self._weather)
        self._publish_info()

    @guarded
    def _on_failure(self, message: str) -> None:
        if self._weather is None:
            self.fail(f"Hava durumuna ulaşılamıyor: {message}")
            return
        self._stale = True
        self._publish_info()

    def _publish_info(self) -> None:
        if self._weather is None:
            return
        text = self._weather.place
        if self._stale and self._last_ok:
            text += f" · eski veri {self._last_ok:%H:%M}"
        self.set_info(text)

    def _render(self, w: api.Weather) -> None:
        text, kind = api.describe(w.code)
        self._temp.setText(_deg(w.temperature))
        self._desc.setText(text)
        self._feels.setText(f"Hissedilen {round(w.apparent)}°C")
        self._icon.set_kind(kind)
        self._backdrop.set_kind(kind)
        self._humidity.setText(f"%{w.humidity}")
        self._wind.setText(f"{round(w.wind_kmh)} km/s")
        self._rain.setText(f"{w.precipitation_mm:.1f} mm".replace(".", ","))
        today = datetime.now().date()
        for (name, value, icon), day in zip(self._day_labels, w.days, strict=False):
            name.setText(day_label(day.day, today))
            icon.set_kind(api.describe(day.code)[1])
            value.setText(f"{_deg(day.temp_min)} / {_deg(day.temp_max)}")

    # --- Yaşam döngüsü ------------------------------------------------------

    def on_show(self) -> None:
        # Panel uzun süre sonra açıldıysa veri bayatsa hemen tazele.
        if self._is_old():
            self._poller.refresh()

    def shutdown(self) -> None:
        self._poller.stop()


def _create(context: CardContext) -> Card:
    return WeatherCard(context)


SPEC = CardSpec(id="weather", title="Hava durumu", icon="", factory=_create)


__all__ = ["SPEC", "WeatherCard"]
