"""Tema katmanı: belirteçler, stil sayfası ve ayarlardan çözümlenen `Look`."""

from __future__ import annotations

from dataclasses import dataclass

from ceyrek_tracker.theme.stylesheet import build_stylesheet
from ceyrek_tracker.theme.tokens import DENSITIES, THEMES, Metrics, Theme, rgba


@dataclass(frozen=True)
class Look:
    """Bir görünümün tamamı: tema renkleri + yoğunluk/yazı ölçeği + cam ayarı."""

    theme: Theme
    metrics: Metrics
    blur: bool = True

    @property
    def stylesheet(self) -> str:
        return build_stylesheet(self.theme, self.metrics)

    @property
    def tint(self) -> str:
        """Panel zemininin saydam rengi (cam ya da düz yarı saydam boyama için)."""
        return rgba(self.theme.bg, self.theme.glass_opacity)


def resolve_look(
    theme_name: str,
    density: str,
    font_scale: float,
    accent: str | None = None,
    glass_opacity: float | None = None,
    blur: bool = True,
) -> Look:
    theme = THEMES.get(theme_name, THEMES["dark"])
    if accent:
        theme = theme.with_accent(accent)
    if glass_opacity is not None:
        theme = theme.with_glass_opacity(glass_opacity)
    metrics = Metrics(spacing=DENSITIES.get(density, 1.0), font=font_scale)
    return Look(theme=theme, metrics=metrics, blur=blur)


__all__ = ["Look", "Metrics", "Theme", "resolve_look"]
