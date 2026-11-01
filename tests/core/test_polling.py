import threading

import pytest

from ceyrek_tracker.core.polling import Poller, retry_delay


@pytest.mark.parametrize(
    ("failures", "interval", "expected"),
    [(0, 60, 60), (1, 60, 10), (2, 60, 20), (3, 60, 40), (4, 60, 60), (10, 300, 300)],
)
def test_retry_delay(failures, interval, expected):
    assert retry_delay(failures, interval) == expected


@pytest.fixture
def make_poller(qtbot):
    pollers = []

    def make(fetch, interval=60):
        poller = Poller(fetch, interval)
        pollers.append(poller)
        return poller

    yield make
    for poller in pollers:
        poller.stop()


def test_success_is_delivered_from_background_thread(qtbot, make_poller):
    threads = []

    def fetch():
        threads.append(threading.current_thread())
        return 42

    poller = make_poller(fetch)
    with qtbot.waitSignal(poller.succeeded, timeout=3000) as blocker:
        poller.start()
    assert blocker.args == [42]
    assert threads[0] is not threading.main_thread()


def test_failure_emits_message_and_keeps_running(qtbot, make_poller):
    def fetch():
        raise RuntimeError("ağ yok")

    poller = make_poller(fetch)
    with qtbot.waitSignal(poller.failed, timeout=3000) as blocker:
        poller.start()
    assert blocker.args == ["ağ yok"]
    assert poller.running


def test_stale_generation_result_is_ignored(qtbot, make_poller):
    gate = threading.Event()

    def slow():
        gate.wait(3)
        return "eski"

    poller = make_poller(slow)
    results = []
    poller.succeeded.connect(results.append)
    poller.start()
    poller.set_fetch(lambda: "yeni")
    qtbot.waitUntil(lambda: results == ["yeni"], timeout=3000)
    gate.set()
    qtbot.wait(100)
    assert results == ["yeni"]


def test_stop_suppresses_results(qtbot, make_poller):
    gate = threading.Event()
    poller = make_poller(lambda: gate.wait(3) or 1)
    results = []
    poller.succeeded.connect(results.append)
    poller.start()
    poller.stop()
    gate.set()
    qtbot.wait(100)
    assert results == []


def test_restart_while_request_is_in_flight_fetches_again(qtbot, make_poller):
    release = threading.Event()
    calls = []

    def fetch():
        calls.append(len(calls))
        if len(calls) == 1:
            release.wait(3)  # ilk istek durdurulurken hâlâ sürüyor
        return len(calls)

    poller = make_poller(fetch)
    poller.start()
    qtbot.waitUntil(lambda: len(calls) == 1, timeout=3000)
    poller.stop()
    with qtbot.waitSignal(poller.succeeded, timeout=3000) as blocker:
        poller.start()
    release.set()
    assert blocker.args == [2]  # eski isteğin sonucu değil, yenisininki
