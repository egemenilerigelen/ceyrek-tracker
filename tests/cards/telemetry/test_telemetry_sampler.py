import sys
from types import SimpleNamespace

import pytest

from ceyrek_tracker.cards.telemetry.gpu import NvidiaReader
from ceyrek_tracker.cards.telemetry.sampler import Sampler

GB = 1024**3


class FakePsutil:
    """Sistemi okumayan psutil: sayaçlar testten ayarlanır."""

    def __init__(self):
        self.cpu = 12.0
        self.freq = SimpleNamespace(current=4680.0)
        self.available = 16 * GB
        self.recv = self.sent = 0

    def cpu_percent(self, interval=None):
        return self.cpu

    def cpu_freq(self):
        if self.freq is None:
            raise NotImplementedError
        return self.freq

    def virtual_memory(self):
        return SimpleNamespace(total=32 * GB, available=self.available)

    def net_io_counters(self):
        return SimpleNamespace(bytes_recv=self.recv, bytes_sent=self.sent)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def ps():
    return FakePsutil()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def sampler(ps, clock):
    return Sampler(
        ps,
        gpu_read=lambda: None,
        clock=clock,
        cpu_name=lambda: "AMD Ryzen 5 7500F 6-Core Processor",
    )


def test_static_values(sampler):
    s = sampler.sample()
    assert s.cpu_name == "AMD Ryzen 5 7500F 6-Core Processor"
    assert s.cpu_percent == 12.0
    assert s.cpu_ghz == pytest.approx(4.68)
    assert (s.memory_used, s.memory_total) == (16 * GB, 32 * GB)
    assert s.memory_percent == 50
    assert s.gpu is None


def test_missing_frequency_is_none(sampler, ps):
    ps.freq = None
    assert sampler.sample().cpu_ghz is None
    ps.freq = SimpleNamespace(current=0)
    assert sampler.sample().cpu_ghz is None


def test_first_sample_has_no_rates(sampler, ps):
    ps.recv = 10**9  # sayaç açılıştan beri birikmiş
    s = sampler.sample()
    assert (s.net_down, s.net_up) == (0, 0)


def test_rates_come_from_counter_differences(sampler, ps, clock):
    sampler.sample()
    clock.now += 2.0
    ps.recv, ps.sent = 4000, 1000
    s = sampler.sample()
    assert (s.net_down, s.net_up) == (2000, 500)


def test_counter_reset_does_not_produce_negative_rates(sampler, ps, clock):
    ps.recv = 5000
    sampler.sample()
    clock.now += 1.0
    ps.recv = 100  # bağdaştırıcı yeniden başladı
    assert sampler.sample().net_down == 0


def test_reset_discards_the_previous_reading(sampler, ps, clock):
    sampler.sample()
    clock.now += 3600  # panel bir saat kapalıydı
    ps.recv = 10**9
    sampler.reset()
    assert sampler.sample().net_down == 0


# --- NVIDIA ----------------------------------------------------------------


class FakeNvml:
    """`pynvml` yerine geçen modül; her çağrı sayılır."""

    NVML_TEMPERATURE_GPU = 0
    NVML_CLOCK_GRAPHICS = 0

    def __init__(self, fail_init=False, no_fan=False):
        self.fail_init = fail_init
        self.no_fan = no_fan
        self.fail_read = False
        self.init_calls = 0
        self.shutdowns = 0

    def nvmlInit(self):
        self.init_calls += 1
        if self.fail_init:
            raise RuntimeError("NVML Shared Library Not Found")

    def nvmlShutdown(self):
        self.shutdowns += 1

    def nvmlDeviceGetHandleByIndex(self, index):
        return object()

    def nvmlDeviceGetName(self, handle):
        return b"NVIDIA GeForce RTX 5060"

    def nvmlDeviceGetUtilizationRates(self, handle):
        if self.fail_read:
            raise RuntimeError("GPU düştü")
        return SimpleNamespace(gpu=3, memory=1)

    def nvmlDeviceGetMemoryInfo(self, handle):
        return SimpleNamespace(used=int(1.6 * GB), total=8 * GB, free=0)

    def nvmlDeviceGetTemperature(self, handle, sensor):
        return 41

    def nvmlDeviceGetPowerUsage(self, handle):
        return 18_400

    def nvmlDeviceGetEnforcedPowerLimit(self, handle):
        return 145_000

    def nvmlDeviceGetClockInfo(self, handle, kind):
        return 577

    def nvmlDeviceGetFanSpeed(self, handle):
        if self.no_fan:
            raise RuntimeError("Not Supported")
        return 0


@pytest.fixture
def nvml(monkeypatch):
    fake = FakeNvml()
    monkeypatch.setitem(sys.modules, "pynvml", fake)
    return fake


def test_nvidia_reading(nvml):
    gpu = NvidiaReader().read()
    assert gpu.name == "NVIDIA GeForce RTX 5060"
    assert gpu.load == 3
    assert (gpu.memory_used, gpu.memory_total) == (int(1.6 * GB), 8 * GB)
    assert gpu.temperature == 41
    assert (gpu.power_watts, gpu.power_limit_watts) == (18.4, 145)
    assert (gpu.clock_mhz, gpu.fan_percent) == (577, 0)


def test_unsupported_sensor_is_none_not_an_error(nvml):
    nvml.no_fan = True
    gpu = NvidiaReader().read()
    assert gpu.fan_percent is None
    assert gpu.load == 3


def test_missing_driver_disables_the_reader_for_good(nvml):
    nvml.fail_init = True
    reader = NvidiaReader()
    assert reader.read() is None
    assert reader.read() is None
    assert nvml.init_calls == 1  # her saniye yeniden denenmez


def test_missing_pynvml_module_is_not_an_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "pynvml", None)  # import ImportError verir
    assert NvidiaReader().read() is None


def test_read_failure_disables_the_reader_and_shuts_nvml_down(nvml):
    reader = NvidiaReader()
    assert reader.read() is not None
    nvml.fail_read = True
    assert reader.read() is None
    nvml.fail_read = False
    assert reader.read() is None  # kapandı, bir daha denemez
    assert nvml.shutdowns == 1


def test_sampler_uses_its_own_nvidia_reader_and_closes_it(nvml, ps):
    sampler = Sampler(ps, cpu_name=lambda: "x")
    assert sampler.sample().gpu.name == "NVIDIA GeForce RTX 5060"
    sampler.close()
    assert nvml.shutdowns == 1
