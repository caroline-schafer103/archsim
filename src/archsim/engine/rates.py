"""Time-varying arrival rates (e.g. traffic spikes)."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RateWindow:
    """Multiply the base rate by `multiplier` during [start, end)."""

    start: float
    end: float
    multiplier: float


@dataclass(frozen=True)
class RateSchedule:
    """A piecewise-constant arrival rate: a base rate plus multiplier windows.

    Overlapping windows multiply together.
    """

    base_rate: float
    windows: list[RateWindow] = field(default_factory=list)

    def rate_at(self, t: float) -> float:
        rate = self.base_rate
        for w in self.windows:
            if w.start <= t < w.end:
                rate *= w.multiplier
        return rate

    def next_change_after(self, t: float) -> float | None:
        """The first time after `t` at which the rate changes, if any."""
        boundaries = [b for w in self.windows for b in (w.start, w.end) if b > t]
        return min(boundaries, default=None)
