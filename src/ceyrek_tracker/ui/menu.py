"""Tepsi ikonu ve widget'a sağ tık için ortak menü."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu, QWidget

from ceyrek_tracker.domain.catalog import GOLD_TYPES
from ceyrek_tracker.providers import PROVIDER_CHOICES
from ceyrek_tracker.settings import REFRESH_CHOICES, Settings
from ceyrek_tracker.ui import theme


class AppMenu(QObject):
    """Menüyü kurar ve seçimleri sinyal olarak bildirir. Durumu `sync` ile güncellenir."""

    toggle_window = Signal()
    refresh_now = Signal()
    featured_selected = Signal(str)
    visibility_toggled = Signal(str, bool)
    provider_selected = Signal(str)
    interval_selected = Signal(int)
    always_on_top_toggled = Signal(bool)
    expanded_toggled = Signal(bool)
    quit_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.menu = QMenu(parent)
        self.menu.setStyleSheet(theme.STYLESHEET)

        self.show_action = self.menu.addAction("Göster / Gizle")
        self.show_action.triggered.connect(self.toggle_window.emit)
        refresh_action = self.menu.addAction("Şimdi yenile")
        refresh_action.triggered.connect(self.refresh_now.emit)
        self.menu.addSeparator()

        featured_menu = self.menu.addMenu("Öne çıkan altın")
        self._featured_group = QActionGroup(self)
        self._featured_actions: dict[str, QAction] = {}
        for gold_type in GOLD_TYPES:
            action = self._radio(featured_menu, self._featured_group, gold_type.name)
            action.triggered.connect(
                lambda _=False, tid=gold_type.id: self.featured_selected.emit(tid)
            )
            self._featured_actions[gold_type.id] = action

        visible_menu = self.menu.addMenu("Listede göster")
        self._visible_actions: dict[str, QAction] = {}
        for gold_type in GOLD_TYPES:
            action = visible_menu.addAction(gold_type.name)
            action.setCheckable(True)
            action.toggled.connect(
                lambda checked, tid=gold_type.id: self.visibility_toggled.emit(tid, checked)
            )
            self._visible_actions[gold_type.id] = action

        provider_menu = self.menu.addMenu("Veri kaynağı")
        self._provider_group = QActionGroup(self)
        self._provider_actions: dict[str, QAction] = {}
        for provider_id, name in PROVIDER_CHOICES:
            action = self._radio(provider_menu, self._provider_group, name)
            action.triggered.connect(
                lambda _=False, pid=provider_id: self.provider_selected.emit(pid)
            )
            self._provider_actions[provider_id] = action
        provider_menu.addSeparator()
        note = provider_menu.addAction("Seçili kaynak yanıt vermezse diğeri denenir")
        note.setEnabled(False)

        interval_menu = self.menu.addMenu("Yenileme aralığı")
        self._interval_group = QActionGroup(self)
        self._interval_actions: dict[int, QAction] = {}
        for seconds, label in REFRESH_CHOICES:
            action = self._radio(interval_menu, self._interval_group, label)
            action.triggered.connect(lambda _=False, s=seconds: self.interval_selected.emit(s))
            self._interval_actions[seconds] = action

        self.menu.addSeparator()
        self._expanded_action = self.menu.addAction("Tüm altınları göster")
        self._expanded_action.setCheckable(True)
        # `triggered`, doğrudan bir Signal(bool).emit'e bağlanınca PySide argümansız
        # sürümü seçip TypeError veriyor; lambda doğru (bool'lu) sürümü seçtirir.
        self._expanded_action.triggered.connect(lambda checked: self.expanded_toggled.emit(checked))
        self._on_top_action = self.menu.addAction("Ekrana sabitle")
        self._on_top_action.setCheckable(True)
        self._on_top_action.triggered.connect(
            lambda checked: self.always_on_top_toggled.emit(checked)
        )

        self.menu.addSeparator()
        quit_action = self.menu.addAction("Çıkış")
        quit_action.triggered.connect(self.quit_requested.emit)

    @staticmethod
    def _radio(menu: QMenu, group: QActionGroup, text: str) -> QAction:
        action = menu.addAction(text)
        action.setCheckable(True)
        group.addAction(action)
        return action

    def sync(self, settings: Settings) -> None:
        """Onay işaretlerini ayarlarla eşitler (sinyal tetiklemeden)."""
        for action in self._all_actions():
            action.blockSignals(True)
        try:
            if action := self._featured_actions.get(settings.featured):
                action.setChecked(True)
            for type_id, action in self._visible_actions.items():
                action.setChecked(type_id in settings.visible)
            if action := self._provider_actions.get(settings.provider):
                action.setChecked(True)
            for seconds, action in self._interval_actions.items():
                action.setChecked(seconds == settings.refresh_seconds)
            self._expanded_action.setChecked(settings.expanded)
            self._on_top_action.setChecked(settings.always_on_top)
        finally:
            for action in self._all_actions():
                action.blockSignals(False)

    def _all_actions(self) -> list[QAction]:
        return [
            *self._featured_actions.values(),
            *self._visible_actions.values(),
            *self._provider_actions.values(),
            *self._interval_actions.values(),
            self._expanded_action,
            self._on_top_action,
        ]
