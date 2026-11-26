"""Time-weighted metrics recorded as the simulation runs."""

import math

from archsim.engine.components import Queue, WorkerPool
from archsim.engine.core import Simulation


def percentile(values: list[float], p: float) -> float:
    """Nearest-rank percentile: the smallest value >= p% of the data."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(p / 100 * len(ordered)))
    return ordered[rank - 1]


def recovery_time(samples: list[tuple[float, int, int]], start: float, end: float) -> float | None:
    """Seconds after `end` until queue depth returns to its level at `start`.

    `samples` are (time, queue_depth, busy_workers) change points, in time order.
    Returns 0 if the queue never rose above its starting level, None if it
    never recovered within the simulation.
    """
    baseline = 0
    for t, depth, _ in samples:
        if t > start:
            break
        baseline = depth

    depth_at_end = baseline
    for t, depth, _ in samples:
        if t <= end:
            depth_at_end = depth
            continue
        if depth_at_end <= baseline:
            return 0.0
        if depth <= baseline:
            return t - end
    return 0.0 if depth_at_end <= baseline else None


class Recorder:
    """Tracks queue depth and worker usage over time.

    Watches one or more stages and records their totals: pass one stage's
    queue and pool for per-stage metrics, or all of them for system-wide ones.

    Averages are time-weighted: a depth of 10 held for 5s counts five times
    as much as a depth of 10 held for 1s.
    """

    def __init__(self, sim: Simulation, queues: list[Queue], pools: list[WorkerPool]) -> None:
        self.queues = queues
        self.pools = pools
        self.samples: list[tuple[float, int, int]] = [(0.0, 0, 0)]
        self.max_queue_depth = 0
        self._last_time = 0.0
        self._last_depth = 0
        self._last_busy = 0
        self.queue_area = 0.0  # integral of queue depth over time
        self.busy_area = 0.0  # integral of busy workers over time
        sim.observe(self._on_step)

    def _on_step(self, now: float) -> None:
        depth = sum(len(q) for q in self.queues)
        busy = sum(p.busy for p in self.pools)
        self._advance(now)
        self.max_queue_depth = max(self.max_queue_depth, depth)
        if (depth, busy) != (self._last_depth, self._last_busy):
            self.samples.append((now, depth, busy))
        self._last_depth, self._last_busy = depth, busy

    def _advance(self, now: float) -> None:
        dt = now - self._last_time
        self.queue_area += self._last_depth * dt
        self.busy_area += self._last_busy * dt
        self._last_time = now

    def finish(self, end: float) -> None:
        self._advance(end)
        self.samples.append((end, self._last_depth, self._last_busy))
