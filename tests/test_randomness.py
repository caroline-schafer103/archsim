"""Random workloads: reproducibility, and agreement with queueing theory."""

import pytest

from archsim import SimConfig, run


def cfg(**overrides) -> SimConfig:
    base = dict(arrival_rate=10, workers=20, service_time=2, duration=60, arrivals="poisson", service="exponential")
    return SimConfig(**{**base, **overrides})


def test_same_seed_same_results():
    assert run(cfg(seed=1)) == run(cfg(seed=1))


def test_different_seeds_differ():
    assert run(cfg(seed=1)).generated != run(cfg(seed=2)).generated


def test_seed_is_recorded_when_not_given():
    r = run(cfg())
    assert r.config.seed is not None
    assert run(r.config) == r  # the recorded seed reproduces the run


def test_worker_count_does_not_change_arrivals():
    # Same seed -> identical arrival stream, so comparisons are fair.
    a = run(cfg(seed=7, workers=5))
    b = run(cfg(seed=7, workers=50))
    assert a.generated == b.generated


def test_poisson_rate_matches_on_average():
    r = run(cfg(seed=3, duration=2000))
    assert r.generated == pytest.approx(10 * 2000, rel=0.03)


def test_exponential_processing_time_matches_on_average():
    r = run(cfg(seed=4, duration=2000, workers=50))
    assert r.avg_processing_time == pytest.approx(2.0, rel=0.05)


def test_mm1_wait_matches_theory():
    # M/M/1 queue: arrival rate 0.5/s, service rate 1/s -> utilization 0.5.
    # Theory: mean wait in queue = rho / (mu - lambda) = 0.5 / 0.5 = 1s.
    r = run(cfg(seed=5, arrival_rate=0.5, workers=1, service_time=1, duration=200_000))
    assert r.avg_wait_time == pytest.approx(1.0, rel=0.05)
    assert r.utilization == pytest.approx(0.5, rel=0.03)


def test_variability_creates_queueing_at_full_capacity():
    # Deterministic: 20 workers exactly match 10/s, so nobody waits.
    steady = run(SimConfig(arrival_rate=10, workers=20, service_time=2, duration=600))
    assert steady.avg_wait_time == pytest.approx(0, abs=1e-9)
    # Same averages, but random: a queue builds up.
    noisy = run(cfg(seed=6, duration=600))
    assert noisy.avg_wait_time > 1.0
