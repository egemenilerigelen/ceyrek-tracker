from datetime import datetime

import pytest

from ceyrek_tracker.cards import CARDS, finance
from ceyrek_tracker.cards.finance.card import change_role, info_text, parse_items, stamp
from ceyrek_tracker.cards.finance.catalog import DEFAULT_ITEMS
from ceyrek_tracker.cards.finance.models import Quote, Snapshot
from ceyrek_tracker.cards.finance.providers import AllProvidersFailed, truncgil
from ceyrek_tracker.core.card_base import CardContext
from ceyrek_tracker.core.card_host import CardHost
from ceyrek_tracker.theme import resolve_look
from conftest import load_fixture

LOOK = resolve_look("dark", "normal", 1.0)


class _Cache:
    def __init__(self, snapshot=None):
        self.snapshot = snapshot
        self.saved = []

    def load(self):
        return self.snapshot

    def save(self, snapshot):
        self.saved.append(snapshot)


class _Fetcher:
    def __init__(self, result):
        self.result = result

    def fetch(self):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture
def snapshot(fetched_at):
    return truncgil.parse(load_fixture("truncgil_v3.json"), fetched_at)


@pytest.fixture
def make_card(qtbot):
    cards = []

    def make(config=None, cache=None, fetcher=None):
        card = finance.FinanceCard(
            CardContext(LOOK, config or {}), cache or _Cache(), fetcher or _Fetcher(None)
        )
        qtbot.addWidget(card)
        cards.append(card)
        return card

    yield make
    for card in cards:
        card.shutdown()


def _texts(card, type_id):
    return tuple(label.text() for label in card._rows[type_id])


def test_registered_after_weather():
    assert [spec.id for spec in CARDS][:2] == ["weather", "finance"]


def test_parse_items_filters_unknown_and_duplicates():
    assert parse_items(["gram", "bilinmeyen", "gram", 5, "usd"]) == ("gram", "usd")


@pytest.mark.parametrize("raw", [None, [], ["bilinmeyen"], "usd", 7])
def test_parse_items_falls_back_to_defaults(raw):
    assert parse_items(raw) == DEFAULT_ITEMS


@pytest.mark.parametrize(
    ("change", "role"), [(None, "dim"), (0.0, "row"), (0.004, "row"), (0.5, "up"), (-0.5, "down")]
)
def test_change_role(change, role):
    assert change_role(change) == role


def test_stamp_shows_date_only_when_not_today():
    now = datetime(2026, 10, 31, 12, 0)
    assert stamp(datetime(2026, 10, 31, 9, 5), now) == "09:05"
    assert stamp(datetime(2026, 10, 30, 16, 45), now) == "30.10 16:45"


def _snap(source_id, moment):
    return Snapshot(source_id, source_id.title(), {}, moment, moment)


def test_info_is_empty_for_fresh_data_from_default_source():
    now = datetime(2026, 11, 1, 12, 0)
    assert info_text(_snap("truncgil", datetime(2026, 11, 1, 11, 52)), False, now) == ""


def test_info_shows_time_when_data_is_old_or_stale():
    now = datetime(2026, 11, 1, 12, 0)
    old = _snap("truncgil", datetime(2026, 10, 30, 17, 45))
    assert info_text(old, False, now) == "30.10 17:45"
    assert info_text(old, True, now) == "eski veri 30.10 17:45"
    fresh = _snap("truncgil", datetime(2026, 11, 1, 11, 58))
    assert info_text(fresh, True, now) == "eski veri 11:58"


def test_info_names_the_source_only_for_fallback():
    now = datetime(2026, 11, 1, 12, 0)
    fresh = _snap("altinkaynak", datetime(2026, 11, 1, 11, 59))
    assert info_text(fresh, False, now) == "Altinkaynak"
    old = _snap("altinkaynak", datetime(2026, 11, 1, 11, 0))
    assert info_text(old, False, now) == "Altinkaynak · 11:00"


def test_silver_and_ons_are_not_shown_by_default():
    assert "gumus" not in DEFAULT_ITEMS
    assert "ons" not in DEFAULT_ITEMS


def test_rows_follow_configured_items(make_card):
    card = make_card({"items": ["ceyrek", "usd"]})
    assert list(card._rows) == ["ceyrek", "usd"]


def test_cached_snapshot_is_rendered_without_network(make_card, snapshot):
    cache = _Cache(snapshot)
    card = make_card({"items": ["gram", "ons"]}, cache=cache)
    assert _texts(card, "gram") == ("6.444 ₺", "%-1,13")
    assert _texts(card, "ons")[0] == "$4.022"
    assert card.current_info == "29.10 16:45"  # veri eski olduğu için saat görünür
    assert cache.saved == []  # diskten okunan veri geri yazılmaz


def test_missing_quote_and_missing_change_show_dash(make_card, fetched_at):
    snapshot = Snapshot("a", "Altınkaynak", {"gram": Quote("gram", 6180.0, 6312.0)}, fetched_at)
    card = make_card(cache=_Cache(snapshot))
    assert _texts(card, "gram") == ("6.312 ₺", "—")
    assert _texts(card, "usd") == ("—", "—")
    assert card._rows["gram"][1].property("role") == "dim"


def test_change_color_follows_direction(make_card, snapshot):
    card = make_card({"items": ["gbp", "euro_yok", "eur", "usd"]}, _Cache(snapshot))
    assert card._rows["gbp"][1].property("role") == "up"
    assert card._rows["eur"][1].property("role") == "down"
    assert card._rows["usd"][1].property("role") == "row"


def test_fresh_data_is_saved_and_shown(qtbot, make_card, snapshot):
    cache = _Cache()
    card = make_card(cache=cache, fetcher=_Fetcher(snapshot))
    with qtbot.waitSignal(card._service.snapshot_changed, timeout=3000):
        card.on_show()
    assert cache.saved == [snapshot]
    assert _texts(card, "ceyrek")[0] == "10.632 ₺"
    assert card.current_error == ""


def test_no_data_and_no_network_shows_error_in_card(qtbot, make_card):
    card = make_card(fetcher=_Fetcher(AllProvidersFailed(["Truncgil: kapalı"])))
    card.on_show()
    qtbot.waitUntil(lambda: bool(card.current_error), timeout=3000)
    assert "ulaşılamıyor" in card.current_error


def test_failure_with_cached_data_marks_info_as_stale(qtbot, make_card, snapshot):
    card = make_card(cache=_Cache(snapshot), fetcher=_Fetcher(AllProvidersFailed(["x"])))
    card.on_show()
    assert "eski veri" not in card.current_info  # başlangıçta uyarma
    qtbot.waitUntil(lambda: "eski veri" in card.current_info, timeout=3000)
    assert card.current_info == "eski veri 29.10 16:45"
    assert _texts(card, "gram")[0] == "6.444 ₺"  # eski veri yine de görünür
    assert card.current_error == ""


def test_polling_runs_only_while_panel_is_open(qtbot, make_card, snapshot):
    card = make_card(fetcher=_Fetcher(snapshot))
    card.on_show()
    qtbot.waitUntil(lambda: card._snapshot is not None, timeout=3000)
    card.on_hide()
    assert not card._service._running
    card.on_show()
    assert card._service._running


def test_card_renders_inside_host_without_error(qtbot, snapshot):
    card = finance.FinanceCard(CardContext(LOOK, {}), _Cache(snapshot), _Fetcher(snapshot))
    host = CardHost(finance.SPEC, card, LOOK, animate=False)
    qtbot.addWidget(host)
    host.show()
    assert host._info.text() == "29.10 16:45"
    assert host._error.isHidden()
    card.shutdown()


def test_every_instrument_has_a_badge_symbol():
    from ceyrek_tracker.cards.finance.catalog import INSTRUMENTS
    from ceyrek_tracker.cards.finance.icon import PICTOGRAMS

    assert all(i.symbol for i in INSTRUMENTS)
    # Element simgesi (Au, Ag) kalmadı: madenler çizimle gösterilir.
    assert {i.symbol for i in INSTRUMENTS if i.id in ("gram", "ceyrek", "ons")} <= set(PICTOGRAMS)


def test_each_row_has_a_badge_that_follows_look(make_card):
    card = make_card({"items": ["usd", "gumus"]})
    assert len(card._badges) == 2
    card.set_look(resolve_look("light", "normal", 1.0))
    assert card._badges[0]._color.name() == resolve_look("light", "normal", 1.0).theme.text_dim


def test_silver_has_its_own_icon():
    from ceyrek_tracker.cards.finance.catalog import get_instrument

    assert get_instrument("gumus").symbol != get_instrument("gram").symbol
