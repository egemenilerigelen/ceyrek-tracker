from PySide6.QtWidgets import QWidget

from ceyrek_tracker.core.panel_window import PanelWindow
from ceyrek_tracker.core.settings import Settings
from ceyrek_tracker.theme import resolve_look

CARD_HEIGHT = 200


def _panel(qtbot) -> PanelWindow:
    panel = PanelWindow(resolve_look("dark", "normal", 1.0), Settings(animations=False))
    qtbot.addWidget(panel)
    panel.open_on(panel.screen())
    return panel


def _add_card(qtbot, panel: PanelWindow) -> None:
    card = QWidget()
    card.setFixedHeight(CARD_HEIGHT)
    panel.add_host(card)
    qtbot.wait(1)  # düzenin oturması için olay döngüsünü bir tur çalıştırır


def test_card_width_stays_put_when_content_starts_to_scroll(qtbot):
    panel = _panel(qtbot)
    scroll = panel._scroll
    widths, scrolled = set(), []
    for _ in range(8):
        _add_card(qtbot, panel)
        widths.add(scroll.widget().width())
        scrolled.append(scroll.verticalScrollBar().maximum() > 0)
    assert not scrolled[0] and scrolled[-1]  # sınır gerçekten aşıldı
    assert len(widths) == 1  # çubuk belirirken kartlar daralmadı


def test_card_width_stays_put_when_content_stops_scrolling(qtbot):
    panel = _panel(qtbot)
    cards = []
    for _ in range(8):
        card = QWidget()
        card.setFixedHeight(CARD_HEIGHT)
        panel.add_host(card)
        cards.append(card)
    qtbot.wait(1)
    scroll = panel._scroll
    assert scroll.verticalScrollBar().maximum() > 0
    before = scroll.widget().width()
    for card in cards[3:]:
        card.hide()  # kartlar katlanınca içerik kısalır
    qtbot.wait(1)
    assert scroll.verticalScrollBar().maximum() == 0
    assert scroll.widget().width() == before
