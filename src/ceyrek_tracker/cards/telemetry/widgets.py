"""Telemetri grafikleri: canlı çizgi grafik (Sparkline) ve doluluk çubuğu (Meter)."""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QGridLayout, QSizePolicy, QWidget

from ceyrek_tracker.cards.telemetry.icon import MetricIcon
from ceyrek_tracker.core.widgets import ElidedLabel, make_label, repolish
from ceyrek_tracker.theme import Look

HISTORY = 48  # grafikte görünen son okuma sayısı
GRAPH_WIDTH = 40
SPARK_HEIGHT = 14
METER_HEIGHT = 5
PEN_WIDTH = 1.5
NAME_WIDTH = 72  # ad ve değer sütunları sabit: ayrıntı ve grafikler her okumada kaymasın
VALUE_WIDTH = 40
FILL_ALPHA = 0.22  # çizginin altındaki dolgunun en koyu yeri


class Sparkline(QWidget):
    """Son okumaların çizgisi; en yeni değer sağ kenarda. `None` okuma yapılamadığı anı
    gösterir ve çizgiyi böler.

    Ölçek: `ceiling` verilirse 0..ceiling sabit; verilmezse en büyük değere göre, ama en az
    `floor` kadar (neredeyse boşta bir değer grafiği tavana yapıştırmasın).
    """

    def __init__(self, look: Look, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(look.metrics.sp(GRAPH_WIDTH), look.metrics.sp(SPARK_HEIGHT))
        self._values: list[float | None] = []
        self._ceiling: float | None = None
        self._floor = 1.0
        self._color = QColor(look.theme.accent)

    def set_color(self, color: str) -> None:
        if self._color != QColor(color):
            self._color = QColor(color)
            self.update()

    def set_values(
        self, values: Sequence[float | None], ceiling: float | None = None, floor: float = 1.0
    ) -> None:
        self._values = list(values)[-HISTORY:]
        self._ceiling, self._floor = ceiling, floor
        self.update()

    def values(self) -> list[float | None]:
        return list(self._values)

    def _top(self) -> float:
        if self._ceiling is not None:
            return self._ceiling
        peak = max((v for v in self._values if v is not None), default=0.0)
        return max(self._floor, peak * 1.15)

    def _segments(self) -> list[list[QPointF]]:
        """Kesintisiz okuma dizileri; noktalar widget koordinatında."""
        pad = PEN_WIDTH
        height = self.height() - 2 * pad
        top = self._top()
        step = self.width() / (HISTORY - 1)
        first = HISTORY - len(self._values)
        segments: list[list[QPointF]] = []
        run: list[QPointF] = []
        for index, value in enumerate(self._values):
            if value is None:
                if run:
                    segments.append(run)
                run = []
                continue
            level = min(1.0, max(0.0, value / top))
            run.append(QPointF((first + index) * step, pad + height * (1 - level)))
        if run:
            segments.append(run)
        return segments

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fill_top = QColor(self._color)
        fill_top.setAlphaF(FILL_ALPHA)
        fill_bottom = QColor(self._color)
        fill_bottom.setAlphaF(0.0)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0.0, fill_top)
        gradient.setColorAt(1.0, fill_bottom)
        pen = QPen(self._color, PEN_WIDTH, Qt.PenStyle.SolidLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        for points in self._segments():
            if len(points) < 2:
                continue
            line = QPainterPath(points[0])
            for point in points[1:]:
                line.lineTo(point)
            area = QPainterPath(line)
            area.lineTo(points[-1].x(), self.height())
            area.lineTo(points[0].x(), self.height())
            area.closeSubpath()
            p.fillPath(area, gradient)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(line)


class Meter(QWidget):
    """Yatay doluluk çubuğu: sönük bir iz ve üzerinde tonun rengiyle dolgu."""

    def __init__(self, look: Look, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(look.metrics.sp(GRAPH_WIDTH), look.metrics.sp(SPARK_HEIGHT))
        self._bar_height = look.metrics.sp(METER_HEIGHT)
        self._fraction = 0.0
        self._color = QColor(look.theme.accent)
        self._track = QColor(look.theme.ink)
        self._track.setAlphaF(look.theme.surface_hover_alpha)

    def set_look(self, look: Look) -> None:
        self._track = QColor(look.theme.ink)
        self._track.setAlphaF(look.theme.surface_hover_alpha)
        self.update()

    def set_color(self, color: str) -> None:
        if self._color != QColor(color):
            self._color = QColor(color)
            self.update()

    def set_fraction(self, fraction: float) -> None:
        self._fraction = min(1.0, max(0.0, fraction))
        self.update()

    def fraction(self) -> float:
        return self._fraction

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        top = (self.height() - self._bar_height) / 2
        radius = self._bar_height / 2
        track = QRectF(0, top, self.width(), self._bar_height)
        p.setBrush(self._track)
        p.drawRoundedRect(track, radius, radius)
        if self._fraction > 0:
            # En az bir yuvarlak uç kadar dolgu: %1 bile görünsün.
            width = max(self._bar_height, self.width() * self._fraction)
            p.setBrush(self._color)
            p.drawRoundedRect(QRectF(0, top, width, self._bar_height), radius, radius)


class MetricRow(QWidget):
    """Tek satır: simge, ad, sönük kısa ayrıntı (ör. "4,68 GHz"), grafik ve renkli değer. Grafik
    ve değer aynı tonu paylaşır. Sığmayan ayrıntı "…" ile kısalır; satırın üzerine gelince
    ipucunda tam metin görünür."""

    def __init__(
        self, title: str, icon: str, graph: Sparkline | Meter, look: Look, tone: str = "accent"
    ) -> None:
        super().__init__()
        sp = look.metrics.sp
        self.graph = graph
        self._look = look
        self._tone = tone
        self._icon = MetricIcon(icon, look)
        self._title = ElidedLabel("metric_name")
        self._title.setFixedWidth(sp(NAME_WIDTH))
        # ElidedLabel'ın "yok say" ilkesi sabit sütunu sıfıra indirir; ad sütunu gerçekten sabit.
        self._title.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        self._title.set_full_text(title)
        self._detail = ElidedLabel("metric_detail")
        self._value = make_label("—", "metric")
        self._value.setFixedWidth(sp(VALUE_WIDTH))
        self._value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._value.setProperty("tone", tone)

        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(sp(6))
        grid.setColumnStretch(2, 1)
        center = Qt.AlignmentFlag.AlignVCenter
        for column, widget in enumerate(
            (self._icon, self._title, self._detail, graph, self._value)
        ):
            grid.addWidget(widget, 0, column, center)
        self._apply_tone()

    def title(self) -> str:
        return self._title.full_text()

    def detail(self) -> str:
        return self._detail.full_text()

    def value(self) -> str:
        return self._value.text()

    def tone(self) -> str:
        return self._tone

    def set_view(self, detail: str, value: str, tone: str, tip: str = "") -> None:
        self._detail.set_full_text(detail)
        self._value.setText(value)
        self.setToolTip(tip)
        if tone != self._tone:
            self._tone = tone
            self._apply_tone()

    def set_look(self, look: Look) -> None:
        self._look = look
        self._icon.set_look(look)
        if isinstance(self.graph, Meter):
            self.graph.set_look(look)
        self._apply_tone()

    def _apply_tone(self) -> None:
        self._value.setProperty("tone", self._tone)
        repolish(self._value)
        self.graph.set_color(self._look.theme.tone_color(self._tone))
