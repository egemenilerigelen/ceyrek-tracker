"""Widget penceresinin yapı taşları."""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ceyrek_tracker.domain.catalog import GOLD_TYPES, GoldType, get_gold_type
from ceyrek_tracker.domain.formatting import format_change, format_price
from ceyrek_tracker.domain.models import FeedStatus, Quote, Snapshot, Trend, compare
from ceyrek_tracker.ui import theme

LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter


def _set_class(widget: QWidget, css_class: str) -> None:
    """Qt stil sayfasındaki `.sinif` seçicisi `class` özelliğine bakar."""
    widget.setProperty("class", css_class)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _label(text: str = "", css_class: str | None = None, align=LEFT) -> QLabel:
    label = QLabel(text)
    label.setAlignment(align)
    if css_class:
        label.setProperty("class", css_class)
    return label


class StatusPill(QWidget):
    """Veri durumunu gösteren hap; canlıyken nokta yavaşça nabız gibi atar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("status_pill")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(7, 2, 8, 2)
        layout.setSpacing(5)
        self._dot = QLabel("●")
        self._text = QLabel()
        layout.addWidget(self._dot)
        layout.addWidget(self._text)

        self._color = theme.TEXT_MUTED
        self._dim = False
        self._pulse = QTimer(self)
        self._pulse.setInterval(1100)
        self._pulse.timeout.connect(self._toggle_dot)
        self.set_status(FeedStatus.LOADING)

    @property
    def text(self) -> str:
        return self._text.text()

    def set_status(self, status: FeedStatus) -> None:
        text, color = theme.STATUS_BADGES[status]
        self._color = color
        self._text.setText(text)
        self.setStyleSheet(
            f"QWidget#status_pill {{ background: {theme.rgba(color, 0.13)}; border-radius: 9px; }}"
        )
        self._text.setStyleSheet(
            f"font-size: 9px; font-weight: 600; letter-spacing: 0.6px; color: {color};"
        )
        self._dim = False
        self._paint_dot()
        if status is FeedStatus.LIVE:
            self._pulse.start()
        else:
            self._pulse.stop()

    def _toggle_dot(self) -> None:
        self._dim = not self._dim
        self._paint_dot()

    def _paint_dot(self) -> None:
        alpha = 0.35 if self._dim else 1.0
        self._dot.setStyleSheet(f"font-size: 8px; color: {theme.rgba(self._color, alpha)};")


class FeaturedPanel(QWidget):
    """Öne çıkarılan altın türünün büyük alış/satış gösterimi.

    Türün adı (`name_label`) bu panelin içinde değil, pencerenin başlık çubuğunda
    durur; pencere onu oraya yerleştirir.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.name_label = _label()
        self.name_label.setObjectName("featured_name")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(0)
        grid.addWidget(_label("Alış", "caption"), 0, 0)
        grid.addWidget(_label("Satış", "caption"), 0, 1)
        self.buy_label = _label("—")
        self.sell_label = _label("—")
        grid.addWidget(self.buy_label, 1, 0)
        grid.addWidget(self.sell_label, 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        self.change_label = _label()
        self.change_label.setObjectName("change_line")
        layout.addWidget(self.change_label)
        self.show_quote(get_gold_type("ceyrek"), None, None)

    def show_quote(
        self,
        gold_type: GoldType | None,
        quote: Quote | None,
        previous: Quote | None,
        *,
        has_snapshot: bool = False,
    ) -> None:
        self.name_label.setText(gold_type.name.upper() if gold_type else "")
        if gold_type is None or quote is None:
            self.buy_label.setText("—")
            self.sell_label.setText("—")
            self.buy_label.setStyleSheet(theme.price_style(theme.TEXT_DIM))
            self.sell_label.setStyleSheet(theme.price_style(theme.TEXT_DIM))
            # Veri geldiği halde bu tür yoksa kaynak bu türü yayınlamıyor demektir.
            self.change_label.setText("Bu kaynakta veri yok" if has_snapshot else "")
            self._style_change(theme.TEXT_MUTED)
            return

        self.buy_label.setText(format_price(quote.buy, gold_type.currency))
        self.sell_label.setText(format_price(quote.sell, gold_type.currency))
        buy_trend = compare(quote.buy, previous.buy if previous else None)
        sell_trend = compare(quote.sell, previous.sell if previous else None)
        self.buy_label.setStyleSheet(theme.price_style(theme.TREND_COLORS[buy_trend]))
        sell_color = (
            theme.TEXT_SECONDARY
            if sell_trend in (Trend.FLAT, Trend.UNKNOWN)
            else theme.TREND_COLORS[sell_trend]
        )
        self.sell_label.setStyleSheet(theme.price_style(sell_color))

        if quote.change_pct is None:
            self.change_label.setText("Bugün —  ·  kaynak günlük değişim vermiyor")
        else:
            self.change_label.setText(f"Bugün {format_change(quote.change_pct)}")
        self._style_change(theme.change_color(quote.change_pct))

    def _style_change(self, color: str) -> None:
        self.change_label.setStyleSheet(f"color: {color};")


class PriceRow(QWidget):
    """Genişletilmiş listedeki tek satır. Tıklanınca öne çıkarılır (pencere yakalar)."""

    NAME_WIDTH = 116
    VALUE_WIDTH = 72
    CHANGE_WIDTH = 50

    def __init__(self, gold_type: GoldType, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.gold_type = gold_type
        self.setProperty("class", "price_row")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"{gold_type.name} — öne çıkarmak için tıkla")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(0)
        self.name_label = _label(gold_type.name, "row_name")
        self.buy_label = _label("—", "row_value", RIGHT)
        self.sell_label = _label("—", "row_value", RIGHT)
        self.change_label = _label("", "row_change", RIGHT)
        self.name_label.setFixedWidth(self.NAME_WIDTH)
        self.buy_label.setFixedWidth(self.VALUE_WIDTH)
        self.sell_label.setFixedWidth(self.VALUE_WIDTH)
        self.change_label.setFixedWidth(self.CHANGE_WIDTH)
        for w in (self.name_label, self.buy_label, self.sell_label, self.change_label):
            layout.addWidget(w)

    def set_featured(self, featured: bool) -> None:
        _set_class(self.name_label, "row_name row_featured" if featured else "row_name")

    def show_quote(self, quote: Quote | None, previous: Quote | None) -> None:
        if quote is None:
            for w in (self.buy_label, self.sell_label):
                w.setText("—")
                w.setStyleSheet(f"color: {theme.TEXT_DIM};")
            self.change_label.setText("")
            return
        currency = self.gold_type.currency
        for label, value, prev in (
            (self.buy_label, quote.buy, previous.buy if previous else None),
            (self.sell_label, quote.sell, previous.sell if previous else None),
        ):
            label.setText(format_price(value, currency))
            label.setStyleSheet(f"color: {theme.TREND_COLORS[compare(value, prev)]};")
        self.change_label.setText(
            "" if quote.change_pct is None else format_change(quote.change_pct)
        )
        self.change_label.setStyleSheet(f"color: {theme.change_color(quote.change_pct)};")


class PriceList(QWidget):
    """Tüm (görünür) altın türlerinin listesi."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(1)

        divider = QWidget()
        divider.setObjectName("list_divider")
        divider.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        divider.setFixedHeight(1)
        layout.addWidget(divider)

        header = QHBoxLayout()
        header.setContentsMargins(6, 8, 6, 3)
        header.setSpacing(0)
        for text, width, align in (
            ("Tür", PriceRow.NAME_WIDTH, LEFT),
            ("Alış", PriceRow.VALUE_WIDTH, RIGHT),
            ("Satış", PriceRow.VALUE_WIDTH, RIGHT),
            ("Bugün", PriceRow.CHANGE_WIDTH, RIGHT),
        ):
            caption = _label(text, "caption", align)
            caption.setFixedWidth(width)
            header.addWidget(caption)
        layout.addLayout(header)

        self.rows: dict[str, PriceRow] = {}
        for gold_type in GOLD_TYPES:
            row = PriceRow(gold_type)
            self.rows[gold_type.id] = row
            layout.addWidget(row)

    def set_visible_types(self, type_ids: Iterable[str]) -> None:
        wanted = set(type_ids)
        for type_id, row in self.rows.items():
            row.setVisible(type_id in wanted)

    def set_featured(self, type_id: str) -> None:
        for row_id, row in self.rows.items():
            row.set_featured(row_id == type_id)

    def show_snapshot(self, snapshot: Snapshot, previous: Snapshot | None) -> None:
        for type_id, row in self.rows.items():
            row.show_quote(snapshot.get(type_id), previous.get(type_id) if previous else None)
