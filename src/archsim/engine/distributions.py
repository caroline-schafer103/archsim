"""Probability distributions for inter-arrival and processing times.

Each distribution draws from a `random.Random` passed in by the caller, so a
simulation is fully reproducible from its seed.
"""

import random
from dataclasses import dataclass
from typing import Protocol


class Distribution(Protocol):
    @property
    def mean(self) -> float: ...

    def sample(self, rng: random.Random) -> float: ...


@dataclass(frozen=True)
class Constant:
    """Always the same value."""

    value: float

    @property
    def mean(self) -> float:
        return self.value

    def sample(self, rng: random.Random) -> float:
        return self.value


@dataclass(frozen=True)
class Exponential:
    """Memoryless: many short values, occasional long ones.

    Exponential gaps between arrivals produce a Poisson arrival process,
    the standard model for independent users sending requests.
    """

    mean: float

    def sample(self, rng: random.Random) -> float:
        return rng.expovariate(1 / self.mean)
