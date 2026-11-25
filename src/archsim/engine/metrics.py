"""Time-weighted metrics recorded as the simulation runs."""

from archsim.engine.components import Queue, WorkerPool
from archsim.engine.core import Simulation


class Recorder:
    """Tracks queue depth and worker usage over time.

    Averages are time-weighted: a depth of 10 held for 5s counts five times
    as much as a depth of 10 held for 1s.
    """

    def __init__(self, sim: Simulation, queue: Queue, pool: WorkerPool) -> None:
        self.queue = queue
        self.pool = pool
        self.samples: list[tuple[float, int, int]] = [(0.0, 0, 0)]
        self.max_queue_depth = 0
        self._last_time = 0.0
        self._last_depth = 0
        self._last_busy = 0
        self.queue_area = 0.0  # integral of queue depth over time
        self.busy_area = 0.0  # integral of busy workers over time
        sim.observe(self._on_step)

    def _on_step(self, now: float) -> None:
        depth, busy = len(self.queue), self.pool.busy
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
