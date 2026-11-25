"""Discrete-event simulation kernel.

The simulation keeps a virtual clock and a priority queue of scheduled
actions. It repeatedly pops the earliest action, jumps the clock to its time,
and runs it. Actions may schedule further actions. Nothing else lives here:
components (sources, queues, workers) are built on top of `schedule`.
"""

import heapq
import itertools
from collections.abc import Callable

Action = Callable[[], None]


class Simulation:
    def __init__(self) -> None:
        self.now: float = 0.0
        self._heap: list[tuple[float, int, Action]] = []
        # Tie-breaker: actions at the same time run in the order scheduled.
        self._seq = itertools.count()
        self._observers: list[Callable[[float], None]] = []

    def schedule_at(self, time: float, action: Action) -> None:
        if time < self.now:
            raise ValueError(f"Cannot schedule in the past ({time} < {self.now})")
        heapq.heappush(self._heap, (time, next(self._seq), action))

    def schedule(self, delay: float, action: Action) -> None:
        self.schedule_at(self.now + delay, action)

    def observe(self, callback: Callable[[float], None]) -> None:
        """Register a callback run after every action (used for metrics)."""
        self._observers.append(callback)

    def run(self, until: float) -> None:
        """Process all actions scheduled at or before `until`."""
        while self._heap and self._heap[0][0] <= until:
            time, _, action = heapq.heappop(self._heap)
            self.now = time
            action()
            for cb in self._observers:
                cb(self.now)
        self.now = until
