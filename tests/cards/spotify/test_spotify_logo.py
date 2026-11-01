from PySide6.QtCore import QPointF

from ceyrek_tracker.cards.spotify.logo import SpotifyLogo, logo_path
from ceyrek_tracker.theme import resolve_look

LOOK = resolve_look("dark", "normal", 1.0)


def test_logo_is_a_disc_with_three_waves_cut_out():
    path = logo_path()
    assert path.contains(QPointF(12, 3))  # dairenin üst kısmı dolu
    assert path.contains(QPointF(12, 21))  # alt kısmı dolu
    assert not path.contains(QPointF(0.0, 0.0))  # dairenin dışı boş
    for wave_y in (7.7, 11.6, 15.25):  # her dalganın orta noktası oyuk
        assert not path.contains(QPointF(12, wave_y))
    assert path.contains(QPointF(12, 9.7))  # dalgalar arasında dolgu var
    assert path.contains(QPointF(12, 13.4))


def test_logo_widget_draws_and_follows_the_look(qtbot):
    logo = SpotifyLogo(LOOK)
    qtbot.addWidget(logo)
    image = logo.grab().toImage()
    assert not image.isNull()
    light = resolve_look("light", "normal", 1.0)
    logo.set_look(light)
    assert logo._color.name() == light.theme.text_dim
