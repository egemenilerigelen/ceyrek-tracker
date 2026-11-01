"""Finans kartı: döviz, altın ve gümüş fiyatları. Kutu ya da çizim yok, yalnızca yazı."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout

from ceyrek_tracker.cards.finance.cache import SnapshotCache
from ceyrek_tracker.cards.finance.catalog import DEFAULT_ITEMS, get_instrument
from ceyrek_tracker.cards.finance.formatting import format_change, format_price
from ceyrek_tracker.cards.finance.icon import SymbolBadge
from ceyrek_tracker.cards.finance.models import FeedState, FeedStatus, Quote, Snapshot
from ceyrek_tracker.cards.finance.providers import DEFAULT_PROVIDER, build_fetcher, create_providers
from ceyrek_tracker.cards.finance.service import Fetcher, PriceService
from ceyrek_tracker.core.card_base import Card, CardContext, CardSpec, guarded
from ceyrek_tracker.core.widgets import make_label, repolish
from ceyrek_tracker.theme import Look

REFRESH_SECONDS = 60
# Veri bundan eskiyse başlıkta saati gösterilir (hafta sonu, kapalı piyasa, bağlantı sorunu).
OLD_AFTER = timedelta(minutes=15)
EMPTY = "—"


def parse_items(raw: Any) -> tuple[str, ...]:
    """Ayardaki enstrüman listesi: bilinmeyenler ve tekrarlar atılır, geçerli bir şey kalmazsa
    varsayılan liste kullanılır."""
    if isinstance(raw, list):
        ids = dict.fromkeys(i for i in raw if isinstance(i, str) and get_instrument(i))
        if ids:
            return tuple(ids)
    return DEFAULT_ITEMS


def change_role(change_pct: float | None) -> str:
    if change_pct is None:
        return "dim"
    rounded = round(change_pct, 2)
    if rounded == 0:
        return "row"
    return "up" if rounded > 0 else "down"


def stamp(moment: datetime, now: datetime) -> str:
    """Bugünün saati 'HH:MM', daha eskisi (hafta sonu, kapalı piyasa) tarihle birlikte."""
    return f"{moment:%H:%M}" if moment.date() == now.date() else f"{moment:%d.%m %H:%M}"


def info_text(snapshot: Snapshot, stale: bool, now: datetime) -> str:
    """Başlıktaki kısa bilgi. Normalde boş kalır: taze veride saat ve kaynak adı kalabalık yapar.

    Yalnızca işe yaradığında yazar: yedek kaynak devredeyse adı (fiyatlar kaynağa göre
    farklı), veri eskiyse ya da güncelleme başarısızsa saati.
    """
    parts = []
    if snapshot.source_id != DEFAULT_PROVIDER:
        parts.append(snapshot.source_name)
    moment = snapshot.source_time or snapshot.fetched_at
    if stale:
        parts.append(f"eski veri {stamp(moment, now)}")
    elif now - moment > OLD_AFTER:
        parts.append(stamp(moment, now))
    return " · ".join(parts)


class FinanceCard(Card):
    def __init__(
        self,
        context: CardContext,
        cache: SnapshotCache | None = None,
        fetcher: Fetcher | None = None,
    ) -> None:
        super().__init__(context)
        self._items = parse_items(self.config.get("items"))
        self._cache = cache or SnapshotCache()
        self._snapshot = self._cache.load()
        self._saved = self._snapshot  # diskte zaten olan veri tekrar yazılmasın
        self._stale = False
        self._rows: dict[str, tuple[QLabel, QLabel]] = {}  # id -> (satış, değişim)
        self._badges: list[SymbolBadge] = []
        self._build_ui()

        fetcher = fetcher or build_fetcher(create_providers(), DEFAULT_PROVIDER)
        self._service = PriceService(fetcher, REFRESH_SECONDS, self._snapshot, self)
        self._service.snapshot_changed.connect(self._on_snapshot)
        self._service.state_changed.connect(self._on_state)

        if self._snapshot is not None:
            self._render(self._snapshot)
            self._publish_info()

    # --- Arayüz -------------------------------------------------------------

    def _build_ui(self) -> None:
        sp = self.look.metrics.sp
        outer = QVBoxLayout(self)
        outer.setContentsMargins(sp(2), 0, sp(2), sp(2))

        grid = QGridLayout()
        grid.setHorizontalSpacing(sp(8))
        grid.setVerticalSpacing(sp(3))
        grid.setColumnStretch(1, 1)
        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        for row, type_id in enumerate(self._items):
            instrument = get_instrument(type_id)
            sell, change = (make_label(EMPTY, role) for role in ("row_value", "dim"))
            badge = SymbolBadge(instrument.symbol, self.look)
            self._badges.append(badge)
            grid.addWidget(badge, row, 0, Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(make_label(instrument.name, "row"), row, 1)
            grid.addWidget(sell, row, 2, right)
            # Değişim sütunu fiyatın sağında, sola hizalı ve ondan ayrık durur.
            change.setContentsMargins(sp(18), 0, 0, 0)
            grid.addWidget(
                change, row, 3, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            self._rows[type_id] = (sell, change)

        outer.addLayout(grid)

    # --- Veri ---------------------------------------------------------------

    @guarded
    def _on_snapshot(self, snapshot: Snapshot) -> None:
        self._snapshot = snapshot
        self._render(snapshot)
        self._publish_info()
        if snapshot is not self._saved:
            self._cache.save(snapshot)
            self._saved = snapshot

    @guarded
    def _on_state(self, state: FeedState) -> None:
        if state.status is FeedStatus.OFFLINE:
            self.fail("Piyasa verilerine ulaşılamıyor")
            return
        if self.current_error:
            self.clear_error()
        # Başlangıçtaki "son bilinen veri" durumu eski sayılmaz; yalnızca gerçek bir
        # başarısızlık ya da gecikme sonrası uyarılır.
        stale = state.status is FeedStatus.STALE and bool(state.errors or state.last_success)
        if stale != self._stale:
            self._stale = stale
            self._publish_info()

    def _publish_info(self) -> None:
        if self._snapshot is not None:
            self.set_info(info_text(self._snapshot, self._stale, datetime.now()))

    def _render(self, snapshot: Snapshot) -> None:
        for type_id, (sell, change) in self._rows.items():
            quote = snapshot.get(type_id)
            if quote is None:
                for label in (sell, change):
                    label.setText(EMPTY)
                self._set_role(change, "dim")
                continue
            self._show_quote(quote, sell, change)

    def _show_quote(self, quote: Quote, sell: QLabel, change: QLabel) -> None:
        currency = get_instrument(quote.type_id).currency
        sell.setText(format_price(quote.sell, currency))
        change.setText(format_change(quote.change_pct))
        self._set_role(change, change_role(quote.change_pct))

    @staticmethod
    def _set_role(label: QLabel, role: str) -> None:
        if label.property("role") != role:
            label.setProperty("role", role)
            repolish(label)

    def set_look(self, look: Look) -> None:
        super().set_look(look)
        for badge in self._badges:
            badge.set_look(look)

    # --- Yaşam döngüsü ------------------------------------------------------

    def on_show(self) -> None:
        # Panel yalnızca açıkken veri çekilir; açılınca hemen tazelenir.
        self._service.start()

    def on_hide(self) -> None:
        self._service.stop()

    def shutdown(self) -> None:
        self._service.stop()


def _create(context: CardContext) -> Card:
    return FinanceCard(context)


SPEC = CardSpec(id="finance", title="Finans", icon="", factory=_create)


__all__ = ["SPEC", "FinanceCard"]
