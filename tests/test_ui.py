from datetime import datetime

import pytest
from PySide6.QtGui import QIcon

from ceyrek_tracker.domain.models import FeedState, FeedStatus, Quote, Snapshot
from ceyrek_tracker.ui import theme
from ceyrek_tracker.ui.main_window import WidgetWindow, status_text


def _snapshot(source="truncgil", buy=10392.68, sell=10632.48):
    return Snapshot(
        source_id=source,
        source_name=source.title(),
        quotes={
            "ceyrek": Quote("ceyrek", buy, sell, 0.67),
            "ons": Quote("ons", 4024.95, 4025.59, -1.04),
        },
        fetched_at=datetime(2026, 10, 29, 16, 41, 5),
        source_time=datetime(2026, 10, 29, 16, 30, 3),
    )


@pytest.fixture
def window(qtbot):
    w = WidgetWindow(QIcon())
    qtbot.addWidget(w)
    w.allow_close()
    return w


def test_shows_featured_prices_in_turkish_format(window):
    window.show_snapshot(_snapshot())
    panel = window.featured_panel
    assert panel.name_label.text() == "ÇEYREK ALTIN"
    assert panel.buy_label.text() == "10.392,68"
    assert panel.sell_label.text() == "10.632,48"
    assert "▲ %0,67" in panel.change_label.text()


def test_switching_featured_type(window):
    window.show_snapshot(_snapshot())
    window.set_featured("ons")
    assert window.featured_panel.buy_label.text() == "$4.024,95"
    assert window.price_list.rows["ons"].name_label.property("class") == "row_name row_featured"


def test_missing_type_shows_placeholder(window):
    window.show_snapshot(_snapshot())
    window.set_featured("cumhuriyet")
    assert window.featured_panel.buy_label.text() == "—"
    assert "veri yok" in window.featured_panel.change_label.text()


def test_trend_color_on_price_increase(window):
    window.show_snapshot(_snapshot(buy=100))
    window.show_snapshot(_snapshot(buy=110))
    assert theme.UP in window.featured_panel.buy_label.styleSheet()


def test_trend_resets_when_source_changes(window):
    window.show_snapshot(_snapshot(buy=100))
    window.show_snapshot(_snapshot(source="altinkaynak", buy=110))
    assert theme.UP not in window.featured_panel.buy_label.styleSheet()


def test_expand_toggles_list(window, qtbot):
    window.show()
    collapsed = window.sizeHint().height()
    window.set_expanded(True)
    assert window.price_list.isVisible()
    assert window.sizeHint().height() > collapsed


def test_badge_follows_state(window):
    window.set_state(FeedState(FeedStatus.STALE, "Kaynaklara ulaşılamıyor"))
    assert window.badge.text == "GECİKMELİ"
    window.set_state(FeedState(FeedStatus.LIVE))
    assert window.badge.text == "CANLI"


def test_status_text():
    now = datetime(2026, 10, 29, 17, 0)
    snap = _snapshot()
    live = status_text(FeedState(FeedStatus.LIVE), snap, now)
    assert live == "Truncgil · veri 16:30 · kontrol 16:41:05"
    stale = status_text(FeedState(FeedStatus.STALE, "Kaynaklara ulaşılamıyor"), snap, now)
    assert stale == "Kaynaklara ulaşılamıyor · son veri 16:41"
    assert "bekleniyor" in status_text(FeedState(FeedStatus.LOADING), None, now)
