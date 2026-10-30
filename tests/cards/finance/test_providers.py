from datetime import datetime

import pytest

from ceyrek_tracker.cards.finance.catalog import GOLD_TYPES
from ceyrek_tracker.cards.finance.models import Snapshot
from ceyrek_tracker.cards.finance.providers import (
    AllProvidersFailed,
    FallbackFetcher,
    ProviderError,
    altinkaynak,
    build_fetcher,
    truncgil,
)
from conftest import load_fixture


class TestTruncgil:
    def test_parses_all_catalog_types(self, fetched_at):
        snapshot = truncgil.parse(load_fixture("truncgil_v3.json"), fetched_at)
        assert set(snapshot.quotes) == {g.id for g in GOLD_TYPES}
        ceyrek = snapshot.get("ceyrek")
        assert ceyrek.buy == pytest.approx(10392.68)
        assert ceyrek.sell == pytest.approx(10632.48)
        assert ceyrek.change_pct == 0.0
        assert snapshot.get("cumhuriyet").change_pct == pytest.approx(0.67)
        assert snapshot.get("ons").buy == pytest.approx(4021.23)  # "$4.021,23"
        assert snapshot.source_time == datetime(2026, 10, 29, 16, 45, 3)
        assert snapshot.source_id == "truncgil"

    def test_skips_broken_item(self, fetched_at):
        payload = load_fixture("truncgil_v3.json")
        payload["ceyrek-altin"]["Buying"] = "n/a"
        snapshot = truncgil.parse(payload, fetched_at)
        assert snapshot.get("ceyrek") is None
        assert snapshot.get("gram") is not None

    @pytest.mark.parametrize("payload", [[], {}, {"USD": {"Buying": "1"}}, "html"])
    def test_rejects_payload_without_gold(self, payload, fetched_at):
        with pytest.raises(ProviderError):
            truncgil.parse(payload, fetched_at)


class TestAltinkaynak:
    def test_parses_known_codes(self, fetched_at):
        snapshot = altinkaynak.parse(load_fixture("altinkaynak.json"), fetched_at)
        assert set(snapshot.quotes) == set(altinkaynak.CODE_MAP)
        ceyrek = snapshot.get("ceyrek")
        assert ceyrek.buy > 1000 and ceyrek.sell >= ceyrek.buy
        assert ceyrek.change_pct is None
        assert snapshot.get("cumhuriyet") is None  # bu kaynakta yok
        assert snapshot.source_time is not None

    def test_rejects_unexpected_shape(self, fetched_at):
        with pytest.raises(ProviderError):
            altinkaynak.parse({"Kod": "C"}, fetched_at)


class _StubProvider:
    def __init__(self, pid, result):
        self.id = pid
        self.name = pid.title()
        self.result = result
        self.calls = 0

    def fetch(self):
        self.calls += 1
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def _snapshot(source_id: str) -> Snapshot:
    return Snapshot(source_id, source_id, {}, datetime(2026, 1, 1))


class TestFallback:
    def test_uses_first_successful(self):
        a = _StubProvider("a", ProviderError("down"))
        b = _StubProvider("b", _snapshot("b"))
        assert FallbackFetcher([a, b]).fetch().source_id == "b"

    def test_stops_at_first_success(self):
        a = _StubProvider("a", _snapshot("a"))
        b = _StubProvider("b", _snapshot("b"))
        FallbackFetcher([a, b]).fetch()
        assert b.calls == 0

    def test_collects_all_errors(self):
        a = _StubProvider("a", ProviderError("x"))
        b = _StubProvider("b", RuntimeError("bug"))
        with pytest.raises(AllProvidersFailed) as info:
            FallbackFetcher([a, b]).fetch()
        assert len(info.value.errors) == 2

    def test_build_fetcher_orders_primary_first(self):
        providers = {"a": _StubProvider("a", None), "b": _StubProvider("b", None)}
        assert [p.id for p in build_fetcher(providers, "b").providers] == ["b", "a"]
