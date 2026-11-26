"""Building blocks wired together into an architecture graph.

Every component that accepts work exposes `receive(job)`. That single
interface is what lets us later chain arbitrary topologies
(Queue -> Workers -> Queue -> Workers -> ...) without changing the engine.
"""

import random
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from archsim.engine.core import Simulation
from archsim.engine.distributions import Distribution
from archsim.engine.rates import RateSchedule


@dataclass
class Visit:
    """One job's pass through one stage (queue + workers)."""

    stage: str
    enqueued: float
    started: float | None = None
    finished: float | None = None

    @property
    def wait_time(self) -> float | None:
        return None if self.started is None else self.started - self.enqueued

    @property
    def processing_time(self) -> float | None:
        if self.started is None or self.finished is None:
            return None
        return self.finished - self.started


@dataclass
class Job:
    id: int
    arrival_time: float
    end_time: float | None = None  # set when the job leaves the system
    visits: list[Visit] = field(default_factory=list)

    @property
    def latency(self) -> float | None:
        return None if self.end_time is None else self.end_time - self.arrival_time

    @property
    def total_wait(self) -> float:
        return sum(v.wait_time for v in self.visits if v.wait_time is not None)

    @property
    def total_processing(self) -> float:
        return sum(v.processing_time for v in self.visits if v.processing_time is not None)


class Receiver(Protocol):
    def receive(self, job: Job) -> None: ...


class Source:
    """Generates jobs following a (possibly time-varying) arrival rate.

    `gap_for(mean)` returns the distribution of gaps between arrivals for a
    given mean gap: Constant for evenly spaced, Exponential for Poisson.
    The first job arrives after one gap (t = 1/rate for constant arrivals).
    """

    def __init__(
        self,
        sim: Simulation,
        rates: RateSchedule,
        gap_for: Callable[[float], Distribution],
        rng: random.Random,
        target: Receiver,
    ) -> None:
        self.sim = sim
        self.rates = rates
        self.gap_for = gap_for
        self.rng = rng
        self.target = target
        self.generated: list[Job] = []
        self._next_time = 0.0

    def start(self) -> None:
        self._schedule_next()

    def _schedule_next(self) -> None:
        t = self._next_time
        while True:
            gap = self.gap_for(1 / self.rates.rate_at(t)).sample(self.rng)
            # Round away float drift from repeated adds (e.g. 600 x 0.1 != 60.0),
            # which would otherwise make arrivals at the horizon flaky.
            candidate = round(t + gap, 9)
            change = self.rates.next_change_after(t)
            if change is None or candidate <= change:
                break
            # The rate changes before this arrival: redraw from the change point
            # at the new rate. Exact for Poisson arrivals (they're memoryless).
            t = change
        self._next_time = candidate
        self.sim.schedule_at(candidate, self._emit)

    def _emit(self) -> None:
        job = Job(id=len(self.generated), arrival_time=self.sim.now)
        self.generated.append(job)
        self.target.receive(job)
        self._schedule_next()


class Queue:
    """FIFO buffer in front of a stage. Notifies its consumer whenever work arrives."""

    def __init__(self, sim: Simulation, stage: str) -> None:
        self.sim = sim
        self.stage = stage
        self._items: deque[Job] = deque()
        self.consumer: "WorkerPool | None" = None
        self.visits: list[Visit] = []  # every job that has entered this stage

    def __len__(self) -> int:
        return len(self._items)

    def receive(self, job: Job) -> None:
        visit = Visit(stage=self.stage, enqueued=self.sim.now)
        job.visits.append(visit)
        self.visits.append(visit)
        self._items.append(job)
        if self.consumer:
            self.consumer.pull()

    def pop(self) -> Job:
        return self._items.popleft()


class WorkerPool:
    """N identical workers pulling from a queue, each handling one job at a time."""

    def __init__(
        self,
        sim: Simulation,
        queue: Queue,
        size: int,
        service_time: Distribution,
        rng: random.Random,
        downstream: Receiver,
    ) -> None:
        self.sim = sim
        self.queue = queue
        self.size = size
        self.service_time = service_time
        self.rng = rng
        self.downstream = downstream
        self.busy = 0
        queue.consumer = self

    def pull(self) -> None:
        while self.busy < self.size and len(self.queue) > 0:
            self._start(self.queue.pop())

    def _start(self, job: Job) -> None:
        job.visits[-1].started = self.sim.now
        self.busy += 1
        self.sim.schedule(self.service_time.sample(self.rng), lambda: self._finish(job))

    def _finish(self, job: Job) -> None:
        job.visits[-1].finished = self.sim.now
        self.busy -= 1
        self.downstream.receive(job)
        self.pull()


class Sink:
    """Terminal node: collects jobs that have left the system."""

    def __init__(self, sim: Simulation) -> None:
        self.sim = sim
        self.completed: list[Job] = []

    def receive(self, job: Job) -> None:
        job.end_time = self.sim.now
        self.completed.append(job)
