import pytest
from PySide6.QtGui import QImage

from ceyrek_tracker.cards.telemetry import icon
from ceyrek_tracker.cards.telemetry.widgets import HISTORY, Meter, MetricRow, Sparkline
from ceyrek_tracker.theme import resolve_look

LOOK = resolve_look("dark", "normal", 1.0)


@pytest.fixture
def spark(qtbot):
    widget = Sparkline(LOOK)
    qtbot.addWidget(widget)
    return widget


def xs(segments):
    return [[p.x() for p in seg] for seg in segments]


def test_newest_value_is_at_the_right_edge(spark):
    spark.set_values([1, 2, 3])
    (segment,) = spark._segments()
    assert segment[-1].x() == pytest.approx(spark.width())
    assert segment[0].x() < segment[-1].x()


def test_full_history_spans_the_whole_width(spark):
    spark.set_values(list(range(HISTORY)))
    (segment,) = spark._segments()
    assert segment[0].x() == pytest.approx(0)
    assert segment[-1].x() == pytest.approx(spark.width())


def test_gap_splits_the_line(spark):
    spark.set_values([1, 2, None, 3, 4, 5])
    segments = spark._segments()
    assert [len(s) for s in segments] == [2, 3]


def test_fixed_ceiling_scales_to_it(spark):
    spark.set_values([0, 50, 100], ceiling=100)
    low, mid, high = spark._segments()[0]
    assert low.y() > mid.y() > high.y()
    spark.set_values([200], ceiling=100)  # tavanı aşan değer kırpılır
    assert 0 <= spark._segments()[0][0].y() <= spark.height()


def test_floor_keeps_idle_values_low_and_peaks_scale_up(spark):
    spark.set_values([1, 1], floor=25)
    idle_y = spark._segments()[0][0].y()
    spark.set_values([1, 200], floor=25)
    peak = spark._segments()[0]
    assert idle_y > spark.height() * 0.8  # 25'lik tabana göre neredeyse dipte
    assert peak[1].y() < spark.height() * 0.3  # zirve üstte
    assert peak[0].y() > spark.height() * 0.8


def test_empty_and_single_value_paint_without_error(spark):
    spark.set_values([])
    assert not spark.grab().isNull()
    spark.set_values([5])
    assert not spark.grab().isNull()


def test_meter_clamps_and_paints(qtbot):
    meter = Meter(LOOK)
    qtbot.addWidget(meter)
    for fraction, expected in ((-1, 0), (0.4, 0.4), (3, 1)):
        meter.set_fraction(fraction)
        assert meter.fraction() == expected
    meter.set_fraction(0.01)  # çok küçük doluluk bile görünür
    meter.set_color("#ff0000")
    image = meter.grab().toImage()
    assert image.pixelColor(2, image.height() // 2).red() > 150


def test_metric_row_texts_and_tone(qtbot):
    graph = Meter(LOOK)
    metric = MetricRow("Bellek (RAM)", icon.MEMORY, graph, LOOK, "cyan")
    qtbot.addWidget(metric)
    metric.set_view("15,2 / 31,6 GB", "%48", "cyan")
    assert (metric.title(), metric.detail(), metric.value()) == (
        "Bellek (RAM)",
        "15,2 / 31,6 GB",
        "%48",
    )
    assert graph._color.name() == LOOK.theme.tone_color("cyan")
    metric.set_view("x", "%95", "down")
    assert metric.tone() == "down"
    assert metric._value.property("tone") == "down"
    assert graph._color.name() == LOOK.theme.tone_color("down")


def test_long_text_is_elided_not_stretched(qtbot):
    metric = MetricRow("Video Belleği", icon.VRAM, Meter(LOOK), LOOK)
    qtbot.addWidget(metric)
    metric.setFixedWidth(300)
    metric.set_view("çok uzun bir ayrıntı satırı " * 6, "%1", "accent")
    metric.show()
    assert metric.width() == 300
    assert metric._detail.text().endswith("…")


@pytest.mark.parametrize("kind", icon.KINDS)
def test_every_icon_draws_something(qtbot, kind):
    widget = icon.MetricIcon(kind, LOOK, 40)
    qtbot.addWidget(widget)
    image = widget.grab().toImage().convertToFormat(QImage.Format.Format_ARGB32)
    painted = any(
        image.pixelColor(x, y).alpha() > 0
        for x in range(image.width())
        for y in range(image.height())
    )
    assert painted, kind


def test_icon_follows_the_theme_color(qtbot):
    widget = icon.MetricIcon(icon.CPU, LOOK)
    qtbot.addWidget(widget)
    light = resolve_look("light", "normal", 1.0)
    widget.set_look(light)
    assert widget._color.name() == light.theme.text_dim
