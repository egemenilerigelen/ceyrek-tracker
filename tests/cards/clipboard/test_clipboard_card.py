import pytest
from PySide6.QtCore import QEvent, QMimeData, QObject, Qt, QUrl, Signal
from PySide6.QtGui import QGuiApplication, QImage
from PySide6.QtWidgets import QApplication

from ceyrek_tracker.cards import CARDS, clipboard
from ceyrek_tracker.cards.clipboard.card import CHECK, COPY, EXCLUDE_FORMAT
from ceyrek_tracker.core.card_base import CardContext
from ceyrek_tracker.core.card_host import CardHost
from ceyrek_tracker.theme import resolve_look

LOOK = resolve_look("dark", "normal", 1.0)


class _Clipboard(QObject):
    """Gerçek panoya dokunmayan, QClipboard gibi davranan sahte pano."""

    dataChanged = Signal()

    def __init__(self):
        super().__init__()
        self._mime = None

    def mimeData(self):
        return self._mime

    def setMimeData(self, mime):
        self._mime = mime
        self.dataChanged.emit()

    def setText(self, text):
        mime = QMimeData()
        mime.setText(text)
        self.setMimeData(mime)


@pytest.fixture
def board():
    return _Clipboard()


@pytest.fixture
def make_card(qtbot, board):
    cards = []

    def make(clip=None):
        card = clipboard.ClipboardCard(CardContext(LOOK, {}), clip or board)
        qtbot.addWidget(card)
        card.show()
        cards.append(card)
        return card

    yield make
    for card in cards:
        card.shutdown()


def _shown(card):
    """Görünen satırlar: (metin, düğme simgesi)."""
    return [(row.text, row.copy_button.text()) for row in card._rows if not row.isHidden()]


def test_shows_a_hint_until_something_is_copied(make_card, board):
    card = make_card()
    assert not card._empty.isHidden()
    assert _shown(card) == []
    board.setText("merhaba")
    assert card._empty.isHidden()
    assert _shown(card) == [("merhaba", COPY)]


def test_text_already_on_the_clipboard_is_listed_at_startup(make_card, board):
    board.setText("zaten panoda")
    assert _shown(make_card()) == [("zaten panoda", COPY)]


def test_lists_the_last_five_newest_first(make_card, board):
    card = make_card()
    for number in range(1, 8):
        board.setText(f"metin {number}")
    assert [text for text, _ in _shown(card)] == [f"metin {n}" for n in (7, 6, 5, 4, 3)]


def test_recopying_an_old_entry_moves_it_up(make_card, board):
    card = make_card()
    for text in ("a", "b", "c"):
        board.setText(text)
    board.setText("a")
    assert [text for text, _ in _shown(card)] == ["a", "c", "b"]


def test_multiline_text_is_one_line_in_the_row(make_card, board):
    card = make_card()
    board.setText("satır bir\nsatır iki")
    row = card._rows[0]
    assert row._label.full_text() == "satır bir satır iki"
    assert row.text == "satır bir\nsatır iki"  # kopyalanan metin değişmez


def test_collects_while_the_panel_is_hidden(make_card, board):
    card = make_card()
    card.on_hide()
    board.setText("panel kapalıyken kopyalandı")
    assert _shown(card) == [("panel kapalıyken kopyalandı", COPY)]


def test_images_and_files_are_skipped(make_card, board):
    card = make_card()
    mime = QMimeData()
    mime.setImageData(QImage(4, 4, QImage.Format.Format_RGB32))
    board.setMimeData(mime)
    files = QMimeData()
    files.setUrls([QUrl.fromLocalFile("C:/a.txt")])
    board.setMimeData(files)
    assert _shown(card) == []


def test_a_copied_link_is_kept_even_though_it_also_carries_a_url(make_card, board):
    card = make_card()
    mime = QMimeData()
    mime.setText("https://example.com/sayfa")
    mime.setUrls([QUrl("https://example.com/sayfa")])
    board.setMimeData(mime)
    assert _shown(card) == [("https://example.com/sayfa", COPY)]


def test_password_manager_content_is_skipped(make_card, board):
    card = make_card()
    mime = QMimeData()
    mime.setText("gizli-parola")
    mime.setData(EXCLUDE_FORMAT, b"\x01\x00\x00\x00")
    board.setMimeData(mime)
    assert _shown(card) == []
    board.setText("sıradan metin")
    assert _shown(card) == [("sıradan metin", COPY)]


def test_empty_clipboard_does_not_break_the_card(make_card, board):
    card = make_card()
    board.setMimeData(None)
    assert _shown(card) == []
    assert card.current_error == ""


def test_copy_button_puts_the_text_back_and_confirms(make_card, board, qtbot):
    card = make_card()
    for text in ("birinci", "ikinci"):
        board.setText(text)
    # Satırlar: ikinci (üstte), birinci. Alttakini kopyala.
    card._rows[1].copy_button.click()
    assert board.mimeData().text() == "birinci"
    # Metin en başa taşındı ve onay işareti onun satırında.
    assert _shown(card) == [("birinci", CHECK), ("ikinci", COPY)]
    qtbot.waitUntil(lambda: _shown(card) == [("birinci", COPY), ("ikinci", COPY)], timeout=3000)


def test_confirmation_goes_away_when_the_panel_closes(make_card, board):
    card = make_card()
    board.setText("x")
    card._rows[0].copy_button.click()
    assert _shown(card) == [("x", CHECK)]
    card.on_hide()
    assert _shown(card) == [("x", COPY)]


def test_works_with_the_real_clipboard(make_card, qtbot):
    real = QGuiApplication.clipboard()
    card = make_card(real)
    real.setText("gerçek pano denemesi")
    qtbot.waitUntil(lambda: ("gerçek pano denemesi", COPY) in _shown(card), timeout=3000)


def test_card_is_registered_after_spotify_and_builds_in_a_host(qtbot):
    ids = [spec.id for spec in CARDS]
    assert ids.index("clipboard") == ids.index("spotify") + 1
    card = clipboard.SPEC.factory(CardContext(LOOK, {}))
    host = CardHost(clipboard.SPEC, card, LOOK)
    qtbot.addWidget(host)
    assert clipboard.SPEC.title == "Pano"
    card.shutdown()


def test_history_survives_panel_close_open_and_collapsing(qtbot, board):
    from ceyrek_tracker.core.card_base import CardSpec
    from ceyrek_tracker.core.card_manager import CardManager

    spec = CardSpec(
        "clipboard", "Pano", "", lambda ctx: clipboard.ClipboardCard(ctx, board), icon_factory=None
    )
    manager = CardManager([spec], [], LOOK, animate=False)
    host = manager.hosts[0]
    card = host.card
    qtbot.addWidget(host)
    manager.show_all()
    board.setText("panel açıkken")

    manager.hide_all()  # panel kapandı
    board.setText("panel kapalıyken 1")
    board.setText("panel kapalıyken 2")
    host.set_collapsed(True)  # kart katlı
    board.setText("katlıyken")
    manager.show_all()  # panel yeniden açıldı

    assert card._history.items == (
        "katlıyken",
        "panel kapalıyken 2",
        "panel kapalıyken 1",
        "panel açıkken",
    )
    manager.shutdown()


def test_clicking_anywhere_on_the_row_copies_it(make_card, board, qtbot):
    card = make_card()
    for text in ("birinci", "ikinci"):
        board.setText(text)
    qtbot.mouseClick(card._rows[1]._label, Qt.MouseButton.LeftButton)
    assert board.mimeData().text() == "birinci"
    assert _shown(card)[0] == ("birinci", CHECK)


def test_remove_button_deletes_only_that_row(make_card, board):
    card = make_card()
    for text in ("a", "b", "c"):
        board.setText(text)
    card._rows[1].remove_button.click()
    assert [text for text, _ in _shown(card)] == ["c", "a"]
    assert board.mimeData().text() == "c"  # pano olduğu gibi kalır


def test_removing_the_last_row_brings_the_hint_back(make_card, board):
    card = make_card()
    board.setText("tek")
    card._rows[0].remove_button.click()
    assert _shown(card) == []
    assert not card._empty.isHidden()


def test_removed_text_does_not_come_back_when_the_panel_opens(make_card, board):
    card = make_card()
    board.setText("gizli")
    card._rows[0].remove_button.click()
    card.on_show()
    assert _shown(card) == []
    board.setText("gizli")  # bilerek yeniden kopyalanırsa girer
    assert _shown(card) == [("gizli", COPY)]


def test_remove_button_appears_only_while_hovering_the_row(make_card, board):
    card = make_card()
    board.setText("x")
    row = card._rows[0]
    assert row.remove_button.property("shown") is False
    QApplication.sendEvent(row, QEvent(QEvent.Type.Enter))
    assert row.remove_button.property("shown") is True
    QApplication.sendEvent(row, QEvent(QEvent.Type.Leave))
    assert row.remove_button.property("shown") is False


def test_remove_button_keeps_its_space_so_text_does_not_shift(make_card, board):
    card = make_card()
    board.setText("x")
    row = card._rows[0]
    assert not row.remove_button.isHidden()
