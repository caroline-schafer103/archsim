"""Results checked against answers computable by hand."""

import pytest

from archsim import SimConfig, run


def cfg(**overrides) -> SimConfig:
    base = dict(arrival_rate=10, workers=5, service_time=2, duration=60)
    return SimConfig(**{**base, **overrides})


def test_prd_overloaded_example():
    # 10/s arriving, 5 workers x 0.5/s = 2.5/s capacity.
    r = run(cfg())
    assert r.generated == 600
    # Each worker starts its first job at 0.1..0.5s, then finishes one every 2s:
    # 29 completions per worker by t=60.
    assert r.completed == 145
    assert r.utilization == pytest.approx(1.0, abs=0.01)
    assert r.max_queue_depth > 400  # backlog grows continuously
    assert r.avg_latency > r.config.service_time


def test_enough_workers_keeps_queue_empty():
    # 20 workers x 0.5/s = 10/s capacity == arrival rate.
    r = run(cfg(workers=20))
    assert r.max_queue_depth <= 1
    assert r.avg_wait_time == pytest.approx(0, abs=1e-9)
    assert r.avg_latency == pytest.approx(2.0)


def test_underloaded_system():
    # 1/s arriving, 5 workers -> 2 busy on average -> 40% utilization.
    r = run(cfg(arrival_rate=1))
    assert r.generated == 60
    assert r.completed == 58  # arrivals at t=1..58 finish by t=60
    assert r.max_queue_depth == 0
    assert r.avg_latency == pytest.approx(2.0)
    # Busy time: 58 jobs x 2s + 1s of job 59 = 117s out of 5 x 60 = 300s.
    assert r.utilization == pytest.approx(117 / 300)


@pytest.mark.parametrize("workers", [1, 5, 20, 50])
def test_jobs_are_conserved(workers):
    r = run(cfg(workers=workers))
    assert r.generated == r.completed + r.in_progress_at_end + r.in_queue_at_end


def test_more_workers_never_hurts_throughput():
    results = [run(cfg(workers=w)) for w in (5, 10, 20)]
    throughputs = [r.throughput for r in results]
    assert throughputs == sorted(throughputs)
