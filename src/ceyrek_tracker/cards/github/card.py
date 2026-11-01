"""GitHub kartı: son bir yılın katkı tablosu (en yeni haftalar), toplam ve seri.

Veri herkese açık profil sayfasından gelir, hesap ya da token gerekmez. Kullanıcı adı
`cards` içindeki `github` ayarında `username` ile verilir. Katkılar yavaş değiştiği için
yenileme seyrektir ve panel kapalıyken de sürer.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from ceyrek_tracker.cards.github import api
from ceyrek_tracker.cards.github.cache import ContributionCache, ContributionStore
from ceyrek_tracker.cards.github.icon import GithubIcon
from ceyrek_tracker.cards.github.models import Contributions
from ceyrek_tracker.cards.github.widgets import ContributionGraph
from ceyrek_tracker.core.card_base import Card, CardContext, CardSpec, guarded
from ceyrek_tracker.core.polling import Poller
from ceyrek_tracker.core.widgets import make_frame, make_label
from ceyrek_tracker.infra.http import create_session

DEFAULT_USERNAME = "egemenilerigelen"
DEFAULT_REFRESH_MINUTES = 30


def thousands(value: int) -> str:
    return f"{value:,}".replace(",", ".")


class GithubCard(Card):
    def __init__(self, context: CardContext, cache: ContributionStore | None = None) -> None:
        super().__init__(context)
        self._username = str(self.config.get("username") or DEFAULT_USERNAME).strip()
        minutes = self.config.get("refresh_minutes")
        if not isinstance(minutes, int) or isinstance(minutes, bool) or not 5 <= minutes <= 720:
            minutes = DEFAULT_REFRESH_MINUTES
        self._interval = minutes * 60
        self._cache = cache or ContributionCache()
        self._data = self._cache.load()
        if self._data is not None and self._data.username != self._username:
            self._data = None  # kullanıcı adı değişmiş, eski veri geçersiz
        self._stale = False
        self._last_ok: datetime | None = self._data.fetched_at if self._data else None
        self._session = create_session()
        self._build_ui()
        self.set_info(f"@{self._username}")

        self._poller = Poller(self._fetch, self._interval, self)
        self._poller.succeeded.connect(self._on_success)
        self._poller.failed.connect(self._on_failure)
        self._poller.start(immediate=self._data is None or self._is_old())

        if self._data is not None:
            self._render(self._data)

    # --- Arayüz -------------------------------------------------------------

    def _build_ui(self) -> None:
        sp = self.look.metrics.sp
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        box = make_frame("inner")
        outer.addWidget(box)
        col = QVBoxLayout(box)
        col.setContentsMargins(sp(8), sp(6), sp(8), sp(6))
        col.setSpacing(sp(5))

        self._graph = ContributionGraph(self.look)
        col.addWidget(self._graph)

        summary = QHBoxLayout()
        summary.setSpacing(sp(6))
        self._total = make_label("Veri bekleniyor", "dim")
        self._streak = make_label("", "soft")
        summary.addWidget(self._total, 1)
        summary.addWidget(self._streak)
        col.addLayout(summary)

    def set_look(self, look) -> None:
        super().set_look(look)
        self._graph.set_look(look)

    # --- Veri ---------------------------------------------------------------

    def _is_old(self) -> bool:
        return self._last_ok is None or datetime.now() - self._last_ok > timedelta(
            seconds=self._interval
        )

    def _fetch(self) -> Contributions:
        """Arka plan thread'inde çalışır."""
        data = api.fetch_contributions(self._session, self._username)
        self._cache.save(data)
        return data

    @guarded
    def _on_success(self, data: Contributions) -> None:
        self._data = data
        self._last_ok = data.fetched_at
        self._stale = False
        self.clear_error()
        self._render(data)
        self._publish_info()

    @guarded
    def _on_failure(self, message: str) -> None:
        if self._data is None:
            self.fail(f"GitHub'a ulaşılamıyor: {message}")
            return
        self._stale = True
        self._publish_info()

    def _publish_info(self) -> None:
        text = f"@{self._username}"
        if self._stale and self._last_ok:
            text += f" · eski veri {self._last_ok:%H:%M}"
        self.set_info(text)

    def _render(self, data: Contributions) -> None:
        self._graph.set_days(data.days)
        self._total.setText(f"Son bir yılda {thousands(data.total)} katkı")
        streak = data.streak(datetime.now().date())
        self._streak.setText(f"Seri {streak} gün" if streak else "")

    # --- Yaşam döngüsü ------------------------------------------------------

    def on_show(self) -> None:
        # Panel uzun süre sonra açıldıysa veri bayatsa hemen tazele.
        if self._is_old():
            self._poller.refresh()

    def shutdown(self) -> None:
        self._poller.stop()


def _create(context: CardContext) -> Card:
    return GithubCard(context)


SPEC = CardSpec(id="github", title="GitHub", icon="", factory=_create, icon_factory=GithubIcon)


__all__ = ["SPEC", "GithubCard"]
