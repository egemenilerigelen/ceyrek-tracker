import pytest

from ceyrek_tracker.cards.weather import api
from ceyrek_tracker.cards.weather.backdrop import TINTS, WeatherBackdrop, render_backdrop
from ceyrek_tracker.theme import resolve_look
from ceyrek_tracker.theme.tokens import DARK, LIGHT, contrast_ratio, parse_hex

KINDS = [
    api.KIND_CLEAR,
    api.KIND_PARTLY,
    api.KIND_CLOUDY,
    api.KIND_FOG,
    api.KIND_RAIN,
    api.KIND_SNOW,
    api.KIND_STORM,
]


def test_every_weather_kind_has_a_tint():
    assert set(KINDS) <= set(TINTS)


def _composite(image, x, y, theme):
    """Arka plan pikselinin kart zemini üstündeki görünen rengi."""
    pixel = image.pixelColor(x, y)
    alpha = pixel.alpha() / 255
    base = parse_hex(theme.bg)
    mixed = (
        round(c * alpha + b * (1 - alpha))
        for c, b in zip((pixel.red(), pixel.green(), pixel.blue()), base, strict=True)
    )
    return "#{:02x}{:02x}{:02x}".format(*mixed)


@pytest.mark.parametrize("theme", [DARK, LIGHT])
@pytest.mark.parametrize("kind", KINDS)
def test_text_stays_readable_over_the_whole_card(theme, kind, qapp):
    width, height = 320, 150
    image = render_backdrop(kind, width, height, theme.ink).toImage()
    worst = {"text": 99.0, "text_soft": 99.0, "text_dim": 99.0}
    for y in range(height):
        for x in range(width):
            if x > 0.75 * width and y < 0.45 * height:
                continue  # simgenin durduğu köşede metin yok
            color = _composite(image, x, y, theme)
            for name in worst:
                worst[name] = min(worst[name], contrast_ratio(getattr(theme, name), color))
    # Tek bir en kötü piksel (tane, yağmur çizgisi dahil) için bile.
    assert worst["text"] >= 7 and worst["text_soft"] >= 4.5, (theme.name, kind, worst)
    assert worst["text_dim"] >= 3.8, (theme.name, kind, worst)  # küçük etiketler


@pytest.mark.parametrize("kind", KINDS)
def test_backdrop_stays_translucent_and_leaves_text_side_calm(kind, qapp):
    image = render_backdrop(kind, 320, 150, "#ffffff").toImage()
    alphas = [[image.pixelColor(x, y).alpha() for x in range(320)] for y in range(150)]
    assert max(max(row) for row in alphas) <= 0.4 * 255
    left = [alphas[y][x] for y in range(30, 70) for x in range(10, 90)]
    right = [alphas[y][x] for y in range(10, 50) for x in range(230, 310)]
    assert sum(left) / len(left) < sum(right) / len(right)


def test_backdrop_is_deterministic(qapp):
    a = render_backdrop(api.KIND_RAIN, 200, 100, "#ffffff").toImage()
    b = render_backdrop(api.KIND_RAIN, 200, 100, "#ffffff").toImage()
    assert a == b


def test_backdrop_frame_follows_weather_kind(qtbot):
    frame = WeatherBackdrop(resolve_look("dark", "normal", 1.0))
    qtbot.addWidget(frame)
    frame.resize(200, 100)
    frame.grab()
    first = frame._cache
    frame.set_kind(api.KIND_SNOW)
    assert frame._cache is None
    frame.grab()
    assert frame._cache is not first
