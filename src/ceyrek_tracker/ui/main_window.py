"""Çerçevesiz, sürüklenebilir masaüstü widget penceresi.

Pencere yalnızca gösterimden sorumludur: ayarları kendisi değiştirmez, kullanıcı
etkileşimlerini sinyal olarak dışarı (AppController'a) bildirir.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QCloseEvent, QContextMenuEvent, QIcon, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ceyrek_tracker import APP_DISPLAY_NAME
from ceyrek_tracker.domain.catalog import DEFAULT_FEATURED, get_gold_type
from ceyrek_tracker.domain.models import FeedState, FeedStatus, Snapshot
from ceyrek_tracker.ui import theme
from ceyrek_tracker.ui.widgets import FeaturedPanel, PriceList, PriceRow, StatusPill

WINDOW_WIDTH = 340


def _clock(dt: datetime, now: datetime) -> str:
    return dt.strftime("%H:%M") if dt.date() == now.date() else dt.strftime("%d.%m %H:%M")


def status_text(state: FeedState, snapshot: Snapshot | None, now: datetime) -> str:
    if snapshot is None:
        if state.status is FeedStatus.OFFLINE:
            return "Kaynaklara ulaşılamıyor · yeniden deneniyor"
        return "Veri bekleniyor..."
    if state.status is FeedStatus.LIVE:
        parts = [snapshot.source_name]
        if snapshot.source_time:
            parts.append(f"veri {_clock(snapshot.source_time, now)}")
        parts.append(f"kontrol {snapshot.fetched_at:%H:%M:%S}")
        return " · ".join(parts)
    message = state.message or "Veri güncel değil"
    return f"{message} · son veri {_clock(snapshot.fetched_at, now)}"


class WidgetWindow(QWidget):
    featured_clicked = Signal(str)
    expand_toggled = Signal(bool)
    context_menu_requested = Signal(QPoint)
    hidden_to_tray = Signal()

    def __init__(self, icon: QIcon, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.setWindowIcon(icon)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowMinimizeButtonHint
        )
        # Yuvarlatılmış köşelerin arkası saydam kalsın.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(theme.STYLESHEET)

        self._snapshot: Snapshot | None = None
        self._previous: Snapshot | None = None
        self._state = FeedState(FeedStatus.LOADING)
        self._featured = DEFAULT_FEATURED
        self._expanded = False
        self._allow_close = False
        self._press_offset: QPoint | None = None
        self._press_global: QPoint | None = None
        self._dragging = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        # Pencere boyutu içeriğe göre otomatik: liste açılınca uzar, kapanınca kısalır.
        outer.setSizeConstraint(QLayout.SizeConstraint.SetFixedSize)

        root = QWidget()
        root.setObjectName("root")
        root.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        root.setFixedWidth(WINDOW_WIDTH)
        outer.addWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(16, 12, 14, 12)
        layout.setSpacing(10)

        self.featured_panel = FeaturedPanel()

        # Başlık çubuğu: öne çıkan türün adı, durum hapı ve pencere düğmeleri.
        top = QHBoxLayout()
        top.setSpacing(4)
        top.addWidget(self.featured_panel.name_label)
        top.addStretch()
        self.badge = StatusPill()
        top.addWidget(self.badge)
        top.addSpacing(6)
        self.expand_button = self._nav_button("expand_btn", "▾", "Tüm altınları göster")
        self.expand_button.clicked.connect(lambda: self.expand_toggled.emit(not self._expanded))
        minimize_button = self._nav_button("minimize_btn", "–", "Küçült")
        minimize_button.clicked.connect(self.showMinimized)
        close_button = self._nav_button("close_btn", "✕", "Tepsiye gizle")
        close_button.clicked.connect(self.close)
        for button in (self.expand_button, minimize_button, close_button):
            top.addWidget(button)
        layout.addLayout(top)

        layout.addWidget(self.featured_panel)

        self.price_list = PriceList()
        self.price_list.setVisible(False)
        layout.addWidget(self.price_list)

        self.status_label = QLabel()
        self.status_label.setObjectName("status_line")
        layout.addWidget(self.status_label)

        self.price_list.set_featured(self._featured)
        self._render()

    @staticmethod
    def _nav_button(name: str, text: str, tooltip: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(name)
        button.setProperty("class", "nav")
        button.setToolTip(tooltip)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedSize(18, 18)
        return button

    # --- Dışarıdan çağrılanlar ---------------------------------------------

    def show_snapshot(self, snapshot: Snapshot) -> None:
        # Kaynak değiştiyse önceki fiyatlarla kıyaslamak yanıltıcı olur.
        previous = self._snapshot
        if previous is not None and previous.source_id != snapshot.source_id:
            previous = None
        self._previous = previous
        self._snapshot = snapshot
        if self._snapshot is not None:
            self.price_list.show_snapshot(snapshot, self._previous)
        self._render()

    def set_state(self, state: FeedState) -> None:
        self._state = state
        self.badge.set_status(state.status)
        self._render_status()

    def set_featured(self, type_id: str) -> None:
        self._featured = type_id
        self.price_list.set_featured(type_id)
        self._render()

    def set_visible_types(self, type_ids: Iterable[str]) -> None:
        self.price_list.set_visible_types(type_ids)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self.price_list.setVisible(expanded)
        self.expand_button.setText("▴" if expanded else "▾")
        self.expand_button.setToolTip("Listeyi gizle" if expanded else "Tüm altınları göster")

    def set_always_on_top(self, on_top: bool) -> None:
        was_visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on_top)
        # setWindowFlag pencereyi gizler; görünürse yeniden göster.
        if was_visible:
            self.show()

    def allow_close(self) -> None:
        """Uygulamadan gerçekten çıkılırken closeEvent'in pencereyi kapatmasına izin ver."""
        self._allow_close = True

    def bring_to_front(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # --- Çizim --------------------------------------------------------------

    def _render(self) -> None:
        gold_type = get_gold_type(self._featured)
        quote = self._snapshot.get(self._featured) if self._snapshot else None
        previous = self._previous.get(self._featured) if self._previous else None
        self.featured_panel.show_quote(
            gold_type, quote, previous, has_snapshot=self._snapshot is not None
        )
        self._render_status()

    def _render_status(self) -> None:
        self.status_label.setText(status_text(self._state, self._snapshot, datetime.now()))
        self.status_label.setToolTip("\n".join(self._state.errors))

    # --- Olaylar ------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_global = event.globalPosition().toPoint()
            self._press_offset = self._press_global - self.frameGeometry().topLeft()
            self._dragging = False
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._press_offset is None or not event.buttons() & Qt.MouseButton.LeftButton:
            return
        current = event.globalPosition().toPoint()
        if not self._dragging:
            distance = (current - self._press_global).manhattanLength()
            self._dragging = distance >= QApplication.startDragDistance()
        if self._dragging:
            self.move(current - self._press_offset)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._press_offset is None:
            return
        was_drag = self._dragging
        self._press_offset = None
        self._dragging = False
        if not was_drag:
            row = self._row_at(event.position().toPoint())
            if row is not None:
                self.featured_clicked.emit(row.gold_type.id)
        event.accept()

    def _row_at(self, pos: QPoint) -> PriceRow | None:
        widget = self.childAt(pos)
        while widget is not None and widget is not self:
            if isinstance(widget, PriceRow):
                return widget
            widget = widget.parentWidget()
        return None

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self.context_menu_requested.emit(event.globalPos())

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            event.accept()
            return
        # Kapatma düğmesi uygulamayı sonlandırmaz; tepsiye gizler.
        event.ignore()
        self.hide()
        self.hidden_to_tray.emit()
