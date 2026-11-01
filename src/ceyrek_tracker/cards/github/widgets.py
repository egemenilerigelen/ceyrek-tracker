"""Katkı tablosu ızgarası: haftalar sütun, günler (pazartesi üstte) satır; en yeni hafta sağda."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta

from PySide6.QtCore import QEvent, QPoint, QRectF, Qt
from PySide6.QtGui import QColor, QHelpEvent, QPainter
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from ceyrek_tracker.cards.github.models import MAX_LEVEL, ContributionDay
from ceyrek_tracker.core.turkish import month_name
from ceyrek_tracker.theme import Look

ROWS = 7
CELL = 9  # kare kenarı; boşluk sütunlar arasında genişliğe göre ayarlanır
MIN_GAP = 2
CELL_RADIUS = 2.0
LEVEL_ALPHAS = (0.0, 0.28, 0.50, 0.75, 1.0)  # seviye 0 vurgu değil, soluk bir iz rengi alır


def tip_text(day: ContributionDay) -> str:
    when = f"{day.day.day} {month_name(day.day)}"
    return f"{day.count} katkı · {when}" if day.count else f"Katkı yok · {when}"


class ContributionGraph(QWidget):
    def __init__(self, look: Look, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cell = look.metrics.sp(CELL)
        self._min_gap = look.metrics.sp(MIN_GAP)
        self._days: dict[date, ContributionDay] = {}
        self._last: date | None = None
        self._set_colors(look)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(ROWS * self._cell + (ROWS - 1) * self._min_gap)

    def set_look(self, look: Look) -> None:
        self._set_colors(look)
        self.update()

    def _set_colors(self, look: Look) -> None:
        empty = QColor(look.theme.ink)
        empty.setAlphaF(look.theme.surface_hover_alpha)
        colors = [empty]
        for alpha in LEVEL_ALPHAS[1 : MAX_LEVEL + 1]:
            tone = QColor(look.theme.accent)
            tone.setAlphaF(alpha)
            colors.append(tone)
        self._colors = colors

    def set_days(self, days: Sequence[ContributionDay]) -> None:
        self._days = {d.day: d for d in days}
        self._last = max(self._days, default=None)
        self.update()

    # --- Yerleşim -----------------------------------------------------------

    def columns(self) -> int:
        """Genişliğe sığan hafta sayısı."""
        return max(1, (self.width() + self._min_gap) // (self._cell + self._min_gap))

    def _gap(self, columns: int) -> float:
        if columns < 2:
            return float(self._min_gap)
        return (self.width() - columns * self._cell) / (columns - 1)

    def _row_gap(self) -> float:
        return (self.height() - ROWS * self._cell) / (ROWS - 1)

    def _column_start(self) -> date | None:
        """En soldaki sütunun haftabaşı (pazartesi)."""
        if self._last is None:
            return None
        newest = self._last - timedelta(days=self._last.weekday())
        return newest - timedelta(weeks=self.columns() - 1)

    def day_at(self, pos: QPoint) -> ContributionDay | None:
        start = self._column_start()
        if start is None:
            return None
        columns = self.columns()
        col_pitch = self._cell + self._gap(columns)
        row_pitch = self._cell + self._row_gap()
        column, row = int(pos.x() // col_pitch), int(pos.y() // row_pitch)
        # Kareler arasındaki boşluğa denk gelen konumlar boş sayılır.
        if not (0 <= column < columns and 0 <= row < ROWS):
            return None
        if pos.x() - column * col_pitch > self._cell or pos.y() - row * row_pitch > self._cell:
            return None
        return self._days.get(start + timedelta(weeks=column, days=row))

    # --- Çizim --------------------------------------------------------------

    def paintEvent(self, event) -> None:
        start = self._column_start()
        if start is None:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        columns = self.columns()
        col_pitch = self._cell + self._gap(columns)
        row_pitch = self._cell + self._row_gap()
        for column in range(columns):
            for row in range(ROWS):
                day = self._days.get(start + timedelta(weeks=column, days=row))
                if day is None:
                    continue
                p.setBrush(self._colors[day.level])
                rect = QRectF(column * col_pitch, row * row_pitch, self._cell, self._cell)
                p.drawRoundedRect(rect, CELL_RADIUS, CELL_RADIUS)

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ToolTip and isinstance(event, QHelpEvent):
            day = self.day_at(event.pos())
            if day is None:
                QToolTip.hideText()
            else:
                QToolTip.showText(event.globalPos(), tip_text(day), self)
            return True
        return super().event(event)
