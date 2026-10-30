import threading
import time
from datetime import datetime, timedelta

import pytest

from ceyrek_tracker.cards.finance.models import FeedStatus, Quote, Snapshot
from ceyrek_tracker.cards.finance.providers import AllProvidersFailed
from ceyrek_tracker.cards.finance.service import PriceService, is_stale, retry_delay


def _snapshot(buy: float = 100.0) -> Snapshot:
    return Snapshot("t", "Test", {"ceyrek": Quote("ceyrek", buy, buy + 5)}, datetime.now())


class _Fetcher:
    def __init__(self, results):
        self.results = list(results)
        self.threads: list[str] = []

    def fetch(self):
        self.threads.append(threading.current_thread().name)
        result = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if isinstance(result, Exception):
            raise result
        return result


@pytest.mark.parametrize(
    ("failures", "interval", "expected"),
    [(0, 60, 60), (1, 60, 10), (2, 60, 20), (3, 60, 40), (4, 60, 60), (10, 300, 300)],
)
def test_retry_delay(failures, interval, expected):
    assert retry_delay(failures, interval) == expected


def test_is_stale():
    now = datetime(2026, 1, 1, 12, 0)
    assert is_stale(None, 60, now)
    assert not is_stale(now - timedelta(seconds=170), 60, now)
    assert is_stale(now - timedelta(seconds=190), 60, now)


@pytest.fixture
def service_factory(qtbot):
    services = []

    def make(fetcher, initial=None):
        service = PriceService(fetcher, interval_seconds=60, initial=initial)
        services.append(service)
        return service

    yield make
    for service in services:
        service.stop()


def test_success_goes_live_off_gui_thread(qtbot, service_factory):
    fetcher = _Fetcher([_snapshot()])
    service = service_factory(fetcher)
    with qtbot.waitSignal(service.snapshot_changed, timeout=3000) as blocker:
        service.start()
    assert blocker.args[0].get("ceyrek").buy == 100.0
    assert service.state.status is FeedStatus.LIVE
    # Ağ isteği ana thread'de değil, ayrı veri thread'inde çalışmalı.
    assert fetcher.threads and fetcher.threads[0] != threading.main_thread().name


def test_failure_without_data_is_offline(qtbot, service_factory):
    service = service_factory(_Fetcher([AllProvidersFailed(["A: kapalı"])]))
    states = []
    service.state_changed.connect(states.append)
    service.start()
    qtbot.waitUntil(lambda: service.state.status is FeedStatus.OFFLINE, timeout=3000)
    assert service.state.errors == ("A: kapalı",)


def test_failure_with_cached_data_is_stale(qtbot, service_factory):
    service = service_factory(_Fetcher([AllProvidersFailed(["x"])]), initial=_snapshot())
    service.start()
    assert service.state.status is FeedStatus.STALE
    qtbot.waitUntil(lambda: bool(service.state.errors), timeout=3000)
    assert service.state.status is FeedStatus.STALE
    assert service.snapshot is not None


def test_unexpected_exception_does_not_kill_service(qtbot, service_factory):
    service = service_factory(_Fetcher([RuntimeError("bug")]))
    service.start()
    qtbot.waitUntil(lambda: service.state.status is FeedStatus.OFFLINE, timeout=3000)


class _BlockingFetcher:
    """İstek, dışarıdan serbest bırakılana kadar bloklanır (takılan ağ isteği gibi)."""

    def __init__(self, source_id: str):
        self.source_id = source_id
        self.started = threading.Event()
        self.release = threading.Event()

    def fetch(self):
        self.started.set()
        assert self.release.wait(timeout=10), "test sonunda serbest bırakılmadı"
        return Snapshot(
            self.source_id, self.source_id, {"ceyrek": Quote("ceyrek", 1, 2)}, datetime.now()
        )


def test_stop_does_not_wait_for_hung_request(qtbot, service_factory):
    # Bloklanan HTTP isteği kesilemez; kapanış onu beklememeli.
    fetcher = _BlockingFetcher("a")
    service = service_factory(fetcher)
    service.start()
    assert fetcher.started.wait(timeout=3)

    started = time.monotonic()
    service.stop()
    assert time.monotonic() - started < 0.5

    fetcher.release.set()  # geç gelen sonuç kapalı servise ulaşmamalı
    qtbot.wait(150)
    assert service.snapshot is None


def test_late_result_from_replaced_fetcher_is_ignored(qtbot, service_factory):
    slow, fast = _BlockingFetcher("slow"), _BlockingFetcher("fast")
    service = service_factory(slow)
    service.start()
    assert slow.started.wait(timeout=3)

    service.set_fetcher(fast)  # önceki istek hâlâ sürerken kaynak değişti
    fast.release.set()
    qtbot.waitUntil(lambda: service.snapshot is not None, timeout=3)
    assert service.snapshot.source_id == "fast"

    slow.release.set()  # yavaş kaynak şimdi cevap veriyor
    qtbot.wait(200)
    assert service.snapshot.source_id == "fast"
    assert service.state.status is FeedStatus.LIVE


def test_set_fetcher_requests_new_data_even_while_request_in_flight(qtbot, service_factory):
    slow, fast = _BlockingFetcher("slow"), _BlockingFetcher("fast")
    service = service_factory(slow)
    service.start()
    assert slow.started.wait(timeout=3)
    service.set_fetcher(fast)
    assert fast.started.wait(timeout=3)
    slow.release.set()
    fast.release.set()
