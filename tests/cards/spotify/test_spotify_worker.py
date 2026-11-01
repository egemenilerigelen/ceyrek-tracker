import threading

from ceyrek_tracker.cards.spotify.worker import Worker


def _collect(worker):
    results = []
    worker.done.connect(lambda tag, value, error: results.append((tag, value, error)))
    return results


def test_job_runs_off_the_main_thread_and_result_returns(qtbot):
    worker = Worker()
    results = _collect(worker)
    worker.submit("id", threading.get_ident)
    qtbot.waitUntil(lambda: bool(results), timeout=2000)
    tag, value, error = results[0]
    assert (tag, error) == ("id", "")
    assert value != threading.get_ident()
    worker.stop()


def test_jobs_run_in_order_on_a_single_thread(qtbot):
    worker = Worker()
    results = _collect(worker)
    for index in range(5):
        worker.submit(str(index), threading.get_ident)
    qtbot.waitUntil(lambda: len(results) == 5, timeout=2000)
    assert [tag for tag, _, _ in results] == ["0", "1", "2", "3", "4"]
    assert len({value for _, value, _ in results}) == 1
    worker.stop()


def test_failing_job_reports_error_and_worker_keeps_going(qtbot):
    worker = Worker()
    results = _collect(worker)

    def boom():
        raise ValueError("bozuk")

    worker.submit("bad", boom)
    worker.submit("good", lambda: 42)
    qtbot.waitUntil(lambda: len(results) == 2, timeout=2000)
    assert results[0] == ("bad", None, "bozuk")
    assert results[1] == ("good", 42, "")
    worker.stop()


def test_prepare_runs_once_on_the_worker_thread(qtbot):
    seen = []
    worker = Worker(prepare=lambda: seen.append(threading.get_ident()))
    results = _collect(worker)
    worker.submit("id", threading.get_ident)
    qtbot.waitUntil(lambda: bool(results), timeout=2000)
    assert seen == [results[0][1]]
    worker.stop()


def test_failing_prepare_does_not_stop_the_worker(qtbot):
    def prepare():
        raise OSError("COM yok")

    worker = Worker(prepare=prepare)
    results = _collect(worker)
    worker.submit("id", lambda: 1)
    qtbot.waitUntil(lambda: bool(results), timeout=2000)
    assert results[0] == ("id", 1, "")
    worker.stop()


def test_stopped_worker_ignores_new_jobs(qtbot):
    worker = Worker()
    results = _collect(worker)
    worker.stop()
    worker.submit("late", lambda: 1)
    qtbot.wait(100)
    assert results == []
