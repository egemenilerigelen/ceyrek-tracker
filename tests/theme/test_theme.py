import pytest

from ceyrek_tracker.theme import resolve_look
from ceyrek_tracker.theme.tokens import DARK, LIGHT, Metrics, blend, contrast_ratio


@pytest.mark.parametrize("theme", [DARK, LIGHT])
def test_text_is_readable_even_on_the_brightest_backdrop(theme):
    # Cam arkasındaki en parlak masaüstü bölgesi kötü senaryo kabul edilir.
    backdrop = "#b8b266" if theme is DARK else "#fffaf0"
    effective = blend(theme.bg, backdrop, theme.glass_opacity)
    for color in (theme.text, theme.text_soft, theme.text_dim, theme.accent):
        assert contrast_ratio(color, effective) >= 4.5, (theme.name, color)


def test_metrics_scale_density_and_fonts():
    assert Metrics(spacing=1.0, font=1.0).sp(10) == 10
    assert Metrics(spacing=0.86).sp(10) == 9
    assert Metrics(font=1.5).fs(12) == 18
    assert Metrics(font=0.1).fs(12) == 8  # okunmayacak kadar küçülmez


def test_look_resolution_and_stylesheet():
    look = resolve_look("light", "compact", 1.2, accent="#112233", glass_opacity=0.5, blur=False)
    assert look.theme.name == "light"
    assert look.theme.accent == "#112233"
    assert look.theme.glass_opacity == 0.5
    assert not look.blur
    assert "#112233" in look.stylesheet
    assert resolve_look("yok", "yok", 1.0).theme.name == "dark"
