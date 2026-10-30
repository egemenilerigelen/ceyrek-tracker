"""Kartın çerçevesi: başlık satırı, katlanma animasyonu ve karta özel hata gösterimi."""

from __future__ import annotations

import logging

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from ceyrek_tracker.core.card_base import Card, CardSpec
from ceyrek_tracker.core.widgets import ClickableFrame, ClickableLabel, make_label
from ceyrek_tracker.theme import Look

logger = logging.getLogger(__name__)

QWIDGETSIZE_MAX = 16777215
CHEVRON_EXPANDED = ""  # aşağı ok
CHEVRON_COLLAPSED = ""  # sağ ok


class CardHost(QWidget):
    collapsed_changed = Signal(str, bool)

    def __init__(
        self,
        spec: CardSpec,
        card: Card | None,
        look: Look,
        collapsed: bool = False,
        animate: bool = True,
        error: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.spec = spec
        self.card = card
        self._animate = animate
        self._collapsed = collapsed
        sp = look.metrics.sp

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)  # başlık-gövde boşluğu gövdenin içinde: katlanınca atlama olmaz

        header = ClickableFrame()
        header.setProperty("role", "card_header")
        header.clicked.connect(self.toggle)
        row = QHBoxLayout(header)
        row.setContentsMargins(0, sp(2), 0, sp(2))
        row.setSpacing(sp(8))
        row.addWidget(make_label(spec.icon, "icon"))
        row.addWidget(make_label(spec.title, "title"))
        row.addStretch()
        self._info = ClickableLabel()
        self._info.setProperty("role", "accent")
        self._info.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        row.addWidget(self._info)
        self._chevron = make_label(CHEVRON_EXPANDED, "icon")
        row.addWidget(self._chevron)
        layout.addWidget(header)

        self._body = QWidget()
        body_layout = QVBoxLayout(self._body)
        body_layout.setContentsMargins(0, sp(6), 0, 0)
        body_layout.setSpacing(sp(6))
        self._error = make_label("", "error", wrap=True)
        self._error.hide()
        body_layout.addWidget(self._error)
        if card is not None:
            body_layout.addWidget(card)
            card.info_changed.connect(self._info.setText)
            card.error_changed.connect(self.set_error)
            self._info.setText(card.current_info)
            if card.info_menu is not None:
                self._info.setCursor(Qt.CursorShape.PointingHandCursor)
                self._info.clicked.connect(self._open_info_menu)
            error = error or card.current_error
        layout.addWidget(self._body)

        self._anim = QPropertyAnimation(self._body, b"maximumHeight", self)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.setDuration(220)
        self._anim.finished.connect(self._on_anim_finished)

        if error:
            self.set_error(error)
        if collapsed:
            self._apply_collapsed_state()

    # --- Katlanma -----------------------------------------------------------

    @property
    def collapsed(self) -> bool:
        return self._collapsed

    def toggle(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool, emit: bool = True) -> None:
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        self._chevron.setText(CHEVRON_COLLAPSED if collapsed else CHEVRON_EXPANDED)
        if self._animate and self.isVisible():
            # Animasyon sürerken yön değişirse (art arda tıklama) şu anki yükseklikten devam
            # edilir; sıfırdan başlatmak kartı bir anda zıplatırdı.
            self._anim.stop()
            start = self._body.height() if self._body.isVisible() else 0
            self._body.setMaximumHeight(start)
            self._body.show()
            end = 0 if collapsed else self._body.sizeHint().height()
            self._anim.setStartValue(start)
            self._anim.setEndValue(end)
            self._anim.start()
        else:
            self._apply_collapsed_state()
        if emit:
            self.collapsed_changed.emit(self.spec.id, collapsed)

    def _apply_collapsed_state(self) -> None:
        self._chevron.setText(CHEVRON_COLLAPSED if self._collapsed else CHEVRON_EXPANDED)
        self._body.setMaximumHeight(0 if self._collapsed else QWIDGETSIZE_MAX)
        self._body.setVisible(not self._collapsed)

    def _on_anim_finished(self) -> None:
        self._apply_collapsed_state()

    def _open_info_menu(self) -> None:
        """Bilgi yazısının altında, sağ kenarı yazıyla hizalı açılır (panel ekranın sağında)."""
        menu = self.card.info_menu
        x = self._info.width() - menu.sizeHint().width()
        menu.popup(self._info.mapToGlobal(QPoint(x, self._info.height())))

    # --- Hata ve yaşam döngüsü ----------------------------------------------

    def set_error(self, message: str) -> None:
        self._error.setText(message)
        self._error.setVisible(bool(message))

    def card_shown(self) -> None:
        self._call("on_show")

    def card_hidden(self) -> None:
        self._anim.stop()
        self._apply_collapsed_state()
        self._call("on_hide")

    def set_look(self, look: Look) -> None:
        if self.card is not None:
            self._call("set_look", look)

    def shutdown(self) -> None:
        self._call("shutdown")

    def _call(self, name: str, *args) -> None:
        """Kartın yaşam döngüsü çağrıları: kartın hatası panele sıçramaz."""
        if self.card is None:
            return
        try:
            getattr(self.card, name)(*args)
        except Exception:
            logger.exception("Kart '%s' %s çağrısında hata verdi", self.spec.id, name)
            self.set_error("Bu kart beklenmedik bir hata verdi. Ayrıntılar log dosyasında.")
