"""Kartın konum menüsünde sunulan şehirler."""

from __future__ import annotations

from ceyrek_tracker.cards.weather import api

DEFAULT_CITY = "Urla"

# Menüdeki konumlar; koordinatlar sabit olduğundan seçimde ağdan konum aranmaz.
PLACES = {
    "Aydın": api.Place("Aydın", "Aydın", 37.8560, 27.8416),
    "Urla": api.Place("Urla", "Urla", 38.3222, 26.7647),
    "İzmir": api.Place("İzmir", "İzmir", 38.4237, 27.1428),
}
