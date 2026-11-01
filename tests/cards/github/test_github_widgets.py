from datetime import date, timedelta

from PySide6.QtCore import QPoint

from ceyrek_tracker.cards.github.icon import GithubIcon
from ceyrek_tracker.cards.github.models import ContributionDay
from ceyrek_tracker.cards.github.widgets import ContributionGraph, tip_text
from ceyrek_tracker.theme import resolve_look

LOOK = resolve_look("dark", "normal", 1.0)
LAST = date(2026, 11, 1)  # pazar


def _year() -> list[ContributionDay]:
    return [ContributionDay(LAST - timedelta(days=i), (i % 5), i % 5) for i in range(364, -1, -1)]


def _graph(qtbot, width=250) -> ContributionGraph:
    graph = ContributionGraph(LOOK)
    qtbot.addWidget(graph)
    graph.resize(width, graph.height())
    graph.set_days(_year())
    return graph


def test_columns_follow_width_and_keep_newest_week_at_right_edge(qtbot):
    narrow, wide = _graph(qtbot, 120), _graph(qtbot, 250)
    assert narrow.columns() < wide.columns()
    # sağ alt köşe: son hafta, pazar satırı = verideki son gün
    corner = QPoint(wide.width() - 2, wide.height() - 2)
    assert wide.day_at(corner).day == LAST


def test_day_at_maps_rows_monday_first_and_skips_gaps(qtbot):
    graph = _graph(qtbot)
    right = graph.width() - 2
    monday = LAST - timedelta(days=6)  # son haftanın pazartesisi
    assert graph.day_at(QPoint(right, 2)).day == monday
    assert graph.day_at(QPoint(-5, 2)) is None
    assert graph.day_at(QPoint(right, graph.height() + 10)) is None
    gap_x = graph._cell + 1  # birinci sütunun hemen sağındaki boşluk
    assert graph.day_at(QPoint(gap_x, 2)) is None


def test_partial_last_week_leaves_future_cells_empty(qtbot):
    graph = ContributionGraph(LOOK)
    qtbot.addWidget(graph)
    graph.resize(250, graph.height())
    graph.set_days([ContributionDay(date(2026, 11, 2), 3, 2)])  # pazartesi, hafta yeni başladı
    right = graph.width() - 2
    assert graph.day_at(QPoint(right, 2)).day == date(2026, 11, 2)
    assert graph.day_at(QPoint(right, graph.height() - 2)) is None  # pazar henüz yok


def test_empty_graph_paints_and_has_no_cells(qtbot):
    graph = ContributionGraph(LOOK)
    qtbot.addWidget(graph)
    graph.resize(250, graph.height())
    graph.grab()
    assert graph.day_at(QPoint(5, 5)) is None


def test_graph_paints_with_data_and_light_look(qtbot):
    graph = _graph(qtbot)
    graph.set_look(resolve_look("light", "compact", 1.0))
    assert not graph.grab().isNull()


def test_tip_text_is_turkish():
    assert tip_text(ContributionDay(date(2026, 7, 5), 8, 3)) == "8 katkı · 5 Temmuz"
    assert tip_text(ContributionDay(date(2026, 7, 5), 0, 0)) == "Katkı yok · 5 Temmuz"


def test_icon_paints(qtbot):
    icon = GithubIcon(LOOK)
    qtbot.addWidget(icon)
    assert not icon.grab().isNull()
