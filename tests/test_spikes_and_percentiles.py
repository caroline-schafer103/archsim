import pytest

from archsim import SimConfig, run
from archsim.engine import RateSchedule, RateWindow, percentile, recovery_time
from archsim.models import Spike


# --- Rate schedule ---------------------------------------------------------


def test_rate_schedule_applies_windows():
    s = RateSchedule(10, [RateWindow(5, 10, 3), RateWindow(8, 12, 2)])
    assert s.rate_at(0) == 10
    assert s.rate_at(5) == 30
    assert s.rate_at(9) == 60  # overlapping windows multiply
    assert s.rate_at(10) == 20  # end is exclusive
    assert s.rate_at(12) == 10


def test_rate_schedule_next_change():
    s = RateSchedule(10, [RateWindow(5, 10, 3)])
    assert s.next_change_after(0) == 5
    assert s.next_change_after(5) == 10
    assert s.next_change_after(10) is None


# --- Spikes in the simulation ----------------------------------------------


def test_constant_spike_arrival_count():
    # 10/s for 10s, 20/s for 10s, 10/s for 10s -> 100 + 200 + 100.
    r = run(SimConfig(arrival_rate=10, workers=50, service_time=1, duration=30,
                      spikes=[Spike(start=10, duration=10, multiplier=2)]))
    assert r.generated == 400


def test_poisson_spike_arrival_count():
    r = run(SimConfig(arrival_rate=10, workers=50, service_time=1, duration=2000,
                      arrivals="poisson", seed=1, spikes=[Spike(start=500, duration=1000, multiplier=3)]))
    # 1000s at 10/s + 1000s at 30/s
    assert r.generated == pytest.approx(40_000, rel=0.02)


def test_recovery_time_matches_hand_calculation():
    # Capacity 12.5/s. Spike: 30/s for 10s -> backlog grows 17.5/s -> ~175 events.
    # Afterwards, spare capacity 2.5/s drains it in ~70s.
    r = run(SimConfig(arrival_rate=10, workers=25, service_time=2, duration=200,
                      spikes=[Spike(start=20, duration=10, multiplier=3)]))
    assert r.spike_recovery[0] == pytest.approx(70, abs=3)


def test_spike_with_headroom_recovers_immediately():
    r = run(SimConfig(arrival_rate=10, workers=100, service_time=2, duration=60,
                      spikes=[Spike(start=20, duration=10, multiplier=3)]))
    assert r.spike_recovery == [0.0]


def test_spike_with_no_spare_capacity_never_recovers():
    # Capacity exactly matches base load, so the backlog can never drain.
    r = run(SimConfig(arrival_rate=10, workers=20, service_time=2, duration=200,
                      spikes=[Spike(start=20, duration=10, multiplier=2)]))
    assert r.spike_recovery == [None]


def test_recovery_time_helper():
    samples = [(0, 0, 0), (10, 5, 1), (20, 3, 1), (25, 0, 1), (30, 0, 0)]
    assert recovery_time(samples, start=5, end=15) == 10  # back to 0 at t=25
    assert recovery_time(samples, start=5, end=40) == 0.0


# --- Percentiles -----------------------------------------------------------


def test_percentile_nearest_rank():
    data = list(range(1, 101))
    assert percentile(data, 50) == 50
    assert percentile(data, 95) == 95
    assert percentile(data, 99) == 99
    assert percentile([], 95) == 0.0


def test_deterministic_percentiles_equal_processing_time():
    r = run(SimConfig(arrival_rate=10, workers=20, service_time=2, duration=60))
    for p in (r.p50_latency, r.p95_latency, r.p99_latency):
        assert p == pytest.approx(2.0)


def test_random_tail_is_longer_than_median():
    r = run(SimConfig(arrival_rate=10, workers=22, service_time=2, duration=600,
                      arrivals="poisson", service="exponential", seed=42))
    assert r.p50_latency < r.avg_latency < r.p95_latency < r.p99_latency
