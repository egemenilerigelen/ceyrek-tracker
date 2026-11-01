from PySide6.QtGui import QColor

from ceyrek_tracker.cards import clipboard
from ceyrek_tracker.cards.clipboard.icon import ClipboardIcon
from ceyrek_tracker.theme import resolve_look

LOOK = resolve_look("dark", "normal", 1.0)


def test_icon_draws_a_clip_and_an_outlined_board(qtbot):
    icon = ClipboardIcon(LOOK)
    qtbot.addWidget(icon)
    image = icon.grab().toImage()
    size = image.width()
    assert size == LOOK.metrics.fs(15)
    # Üstteki kıskaç dolu, altlığın içi boş: iç içe ikinci bir sayfa çizilmez.
    background = image.pixelColor(0, 0)
    assert image.pixelColor(size // 2, int(size * 0.16)) != background
    assert image.pixelColor(size // 2, int(size * 0.6)) == background


def test_icon_follows_the_look(qtbot):
    icon = ClipboardIcon(LOOK)
    qtbot.addWidget(icon)
    light = resolve_look("light", "normal", 1.0)
    icon.set_look(light)
    assert icon._color == QColor(light.theme.text_dim)


def test_card_uses_the_drawn_icon_in_its_header():
    assert clipboard.SPEC.icon_factory is ClipboardIcon
