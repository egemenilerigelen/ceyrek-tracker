from ceyrek_tracker.core.panel_window import PanelWindow
from ceyrek_tracker.core.platform import glass
from ceyrek_tracker.core.settings import Settings
from ceyrek_tracker.theme import resolve_look


def test_glass_surface_keeps_nonzero_alpha_so_clicks_do_not_fall_through(qtbot, monkeypatch):
    # Windows, tamamen saydam (alfa 0) katmanlı pencere pikselinde tıklamayı alttaki uygulamaya
    # geçirir; cam açıkken yüzey görünmez ama sıfır olmayan bir alfa ile boyanmalı.
    monkeypatch.setattr(glass, "enable_glass", lambda *args: True)
    panel = PanelWindow(resolve_look("dark", "normal", 1.0), Settings(animations=False))
    qtbot.addWidget(panel)
    panel.show()
    panel._sync_glass()
    assert panel.glass_active
    assert panel._surface.fill is not None
    assert 0 < panel._surface.fill.alpha() <= 2
