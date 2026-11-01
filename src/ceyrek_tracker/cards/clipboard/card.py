"""Pano kartı: son kopyalanan metinler, her satırın başında bir kopyalama düğmesiyle.

Pano değişimi olay olarak gelir (`dataChanged`), yoklama yoktur. Kart panel kapalıyken de
dinler: kopyalama çoğunlukla panel kapalıyken olur. Geçmiş yalnızca bellekte tutulur,
diske yazılmaz: pano parola gibi gizli şeyler taşıyabilir.
"""

from __future__ import annotations

import contextlib

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QClipboard, QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QToolButton, QVBoxLayout, QWidget

from ceyrek_tracker.cards.clipboard.history import MAX_ITEMS, ClipboardHistory, preview
from ceyrek_tracker.cards.clipboard.icon import ClipboardIcon
from ceyrek_tracker.core.card_base import Card, CardContext, CardSpec, guarded
from ceyrek_tracker.core.widgets import (
    ClickableFrame,
    ElidedLabel,
    make_frame,
    make_label,
    repolish,
)

FLASH_MS = 1200  # kopyalandıktan sonra onay işaretinin görünme süresi
# Parola yöneticilerinin panoya koyarken eklediği işaret: bu metin pano geçmişlerine girmemeli.
EXCLUDE_FORMAT = "ExcludeClipboardContentFromMonitorProcessing"

# Segoe MDL2 Assets karakterleri
PASTE = ""
COPY = ""
CHECK = ""
REMOVE = ""


def _tool(role: str, tooltip: str = "") -> QToolButton:
    button = QToolButton()
    button.setProperty("role", role)
    button.setToolTip(tooltip)
    button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button


class ClipRow(ClickableFrame):
    """Tek satır: solda kopyalama simgesi, ortada tek satıra indirilmiş metin, sağda silme
    düğmesi. Satırın her yerine tıklamak kopyalar; silme düğmesi yalnızca fare satırın
    üzerindeyken görünür (yerini korur, metin kaymaz)."""

    copy_requested = Signal(str)
    remove_requested = Signal(str)

    def __init__(self, spacing: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.text = ""
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(spacing)
        self.copy_button = _tool("copy")
        self.remove_button = _tool("remove", "Sil")
        self.remove_button.setText(REMOVE)
        self.remove_button.setProperty("shown", False)
        self._label = ElidedLabel("row")
        row.addWidget(self.copy_button, 0, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self._label, 1, Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.remove_button, 0, Qt.AlignmentFlag.AlignVCenter)
        self.clicked.connect(lambda: self.copy_requested.emit(self.text))
        self.copy_button.clicked.connect(lambda: self.copy_requested.emit(self.text))
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self.text))

    def enterEvent(self, event: QEvent) -> None:
        self._set_hovered(True)
        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self._set_hovered(False)
        super().leaveEvent(event)

    def _set_hovered(self, hovered: bool) -> None:
        if self.remove_button.property("shown") != hovered:
            self.remove_button.setProperty("shown", hovered)
            repolish(self.remove_button)

    def show_entry(self, text: str, copied: bool) -> None:
        self.text = text
        self._label.set_full_text(preview(text))
        self.copy_button.setText(CHECK if copied else COPY)
        self.copy_button.setToolTip("Kopyalandı" if copied else "Kopyala")
        if self.copy_button.property("active") != copied:
            self.copy_button.setProperty("active", copied)
            repolish(self.copy_button)


class ClipboardCard(Card):
    def __init__(self, context: CardContext, clipboard: QClipboard | None = None) -> None:
        super().__init__(context)
        self._clipboard = clipboard or QGuiApplication.clipboard()
        self._history = ClipboardHistory()
        self._copied: str | None = None  # az önce düğmeyle kopyalanan metin (onay işareti)
        self._flash = QTimer(self)
        self._flash.setSingleShot(True)
        self._flash.setInterval(FLASH_MS)
        self._flash.timeout.connect(self._end_flash)
        self._build_ui()
        self._render()
        self._clipboard.dataChanged.connect(self._on_changed)
        self._capture()  # panoda zaten duran metin

    # --- Arayüz -------------------------------------------------------------

    def _build_ui(self) -> None:
        sp = self.look.metrics.sp
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        box = make_frame("inner")
        outer.addWidget(box)
        rows = QVBoxLayout(box)
        rows.setContentsMargins(sp(6), sp(4), sp(6), sp(4))
        rows.setSpacing(0)

        self._empty = make_label("Kopyaladığın metinler burada görünür", "dim")
        self._empty.setContentsMargins(sp(4), 0, 0, 0)
        rows.addWidget(self._empty)
        self._rows = [ClipRow(sp(4)) for _ in range(MAX_ITEMS)]
        for row in self._rows:
            row.copy_requested.connect(self._copy)
            row.remove_requested.connect(self._remove)
            rows.addWidget(row)

    def _render(self) -> None:
        items = self._history.items
        self._empty.setVisible(not items)
        for index, row in enumerate(self._rows):
            row.setVisible(index < len(items))
            if index < len(items):
                row.show_entry(items[index], items[index] == self._copied)

    # --- Pano ---------------------------------------------------------------

    @guarded
    def _on_changed(self) -> None:
        self._capture()

    def _capture(self) -> None:
        text = self._read()
        if text is not None and self._history.add(text):
            self._render()

    def _read(self) -> str | None:
        """Panodaki metin; metin olmayan içerik (resim, dosya) ve parola yöneticilerinin
        işaretlediği içerik atlanır."""
        data = self._clipboard.mimeData()
        # `hasText()` değil: Qt onu dosya listesi (Explorer'da kopyalanan dosyalar) için de
        # doğru sayar, dosya yolları geçmişe girmesin.
        if data is None or not data.hasFormat("text/plain"):
            return None
        if any(EXCLUDE_FORMAT in name for name in data.formats()):
            return None
        return data.text()

    @guarded
    def _copy(self, text: str) -> None:
        self._copied = text
        self._flash.start()
        self._clipboard.setText(text)  # pano değişimi geçmişte metni en başa taşır
        self._render()

    @guarded
    def _remove(self, text: str) -> None:
        # Panodaki metin silinen olsa bile pano olduğu gibi kalır; yalnızca geçmişten çıkar.
        if self._history.remove(text):
            self._render()

    def _end_flash(self) -> None:
        self._copied = None
        self._render()

    # --- Yaşam döngüsü ------------------------------------------------------

    def on_hide(self) -> None:
        self._flash.stop()
        self._end_flash()

    def shutdown(self) -> None:
        self._flash.stop()
        with contextlib.suppress(RuntimeError, TypeError):
            self._clipboard.dataChanged.disconnect(self._on_changed)


def _create(context: CardContext) -> Card:
    return ClipboardCard(context)


SPEC = CardSpec(
    id="clipboard", title="Pano", icon=PASTE, factory=_create, icon_factory=ClipboardIcon
)


__all__ = ["SPEC", "ClipboardCard"]
