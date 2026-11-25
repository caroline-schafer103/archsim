"""Building blocks wired together into an architecture graph.

Every component that accepts work exposes `receive(job)`. That single
interface is what lets us later chain arbitrary topologies
(Queue -> Workers -> Queue -> Workers -> ...) without changing the engine.
"""

import random
from collections import deque
from dataclasses import dataclass
from typing import Protocol

from archsim.engine.core import Simulation
from archsim.engine.distributions import Distribution


@dataclass
class Job:
    id: int
    arrival_time: float
    start_time: float | None = None
    end_time: float | None = None

    @property
    def wait_time(self) -> float | None:
        return None if self.start_time is None else self.start_time - self.arrival_time

    @property
    def processing_time(self) -> float | None:
        if self.start_time is None or self.end_time is None:
            return None
        return self.end_time - self.start_time

    @property
    def latency(self) -> float | None:
        return None if self.end_time is None else self.end_time - self.arrival_time


class Receiver(Protocol):
    def receive(self, job: Job) -> None: ...


class Source:
    """Generates jobs separated by gaps drawn from `interarrival`.

    The first job arrives after one gap (t = 1/rate for constant arrivals).
    """

    def __init__(
        self,
        sim: Simulation,
        interarrival: Distribution,
        rng: random.Random,
        target: Receiver,
    ) -> None:
        self.sim = sim
        self.interarrival = interarrival
        self.rng = rng
        self.target = target
        self.generated: list[Job] = []
        self._next_time = 0.0

    def start(self) -> None:
        self._schedule_next()

    def _schedule_next(self) -> None:
        # Round away float drift from repeated adds (e.g. 600 x 0.1 != 60.0),
        # which would otherwise make arrivals at the horizon flaky.
        self._next_time = round(self._next_time + self.interarrival.sample(self.rng), 9)
        self.sim.schedule_at(self._next_time, self._emit)

    def _emit(self) -> None:
        job = Job(id=len(self.generated), arrival_time=self.sim.now)
        self.generated.append(job)
        self.target.receive(job)
        self._schedule_next()


class Queue:
    """FIFO buffer. Notifies its consumer whenever work arrives."""

    def __init__(self, sim: Simulation) -> None:
        self.sim = sim
        self._items: deque[Job] = deque()
        self.consumer: "WorkerPool | None" = None

    def __len__(self) -> int:
        return len(self._items)

    def receive(self, job: Job) -> None:
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
        job.start_time = self.sim.now
        self.busy += 1
        self.sim.schedule(self.service_time.sample(self.rng), lambda: self._finish(job))

    def _finish(self, job: Job) -> None:
        job.end_time = self.sim.now
        self.busy -= 1
        self.downstream.receive(job)
        self.pull()


class Sink:
    """Terminal node: collects completed jobs."""

    def __init__(self) -> None:
        self.completed: list[Job] = []

    def receive(self, job: Job) -> None:
        self.completed.append(job)
