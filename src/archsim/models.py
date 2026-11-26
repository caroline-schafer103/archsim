"""Public data contract: what goes into a simulation and what comes out.

These are Pydantic models so the future API (FastAPI) and UI can reuse them
directly for validation and JSON serialization.
"""

from typing import Literal

from pydantic import BaseModel, Field

ArrivalPattern = Literal["constant", "poisson"]
ServicePattern = Literal["constant", "exponential"]


class Spike(BaseModel):
    """A period of increased (or reduced) traffic."""

    start: float = Field(ge=0, description="Seconds into the simulation")
    duration: float = Field(gt=0, description="Seconds the spike lasts")
    multiplier: float = Field(gt=0, description="Arrival rate multiplier, e.g. 3 = triple traffic")

    @property
    def end(self) -> float:
        return self.start + self.duration


class SimConfig(BaseModel):
    """MVP pipeline: Source -> Queue -> WorkerPool -> Sink."""

    name: str = "baseline"
    arrival_rate: float = Field(gt=0, description="Average events per second")
    workers: int = Field(ge=1, description="Number of parallel workers")
    service_time: float = Field(gt=0, description="Average seconds to process one event")
    duration: float = Field(gt=0, description="Simulated seconds to run")
    arrivals: ArrivalPattern = Field(
        "constant", description="constant: evenly spaced; poisson: random, independent arrivals"
    )
    service: ServicePattern = Field(
        "constant", description="constant: every event takes service_time; exponential: random around it"
    )
    seed: int | None = Field(None, description="Random seed; same seed gives identical runs")
    spikes: list[Spike] = Field(default_factory=list, description="Traffic spikes during the run")

    @property
    def is_random(self) -> bool:
        return self.arrivals != "constant" or self.service != "constant"


class Sample(BaseModel):
    """System state at a moment in simulated time."""

    time: float
    queue_depth: int
    busy_workers: int


class SimResults(BaseModel):
    config: SimConfig

    # Counts
    generated: int
    completed: int
    in_queue_at_end: int
    in_progress_at_end: int

    # Queue
    avg_queue_depth: float = Field(description="Time-weighted average")
    max_queue_depth: int

    # Timing (seconds)
    avg_wait_time: float = Field(description="Queue wait, over jobs that started")
    avg_processing_time: float = Field(description="Over completed jobs")
    avg_latency: float = Field(description="Arrival to completion, over completed jobs")
    p50_latency: float = Field(description="Median latency, over completed jobs")
    p95_latency: float = Field(description="95% of completed jobs finished within this")
    p99_latency: float = Field(description="99% of completed jobs finished within this")

    # Spikes
    spike_recovery: list[float | None] = Field(
        description="Per spike: seconds after it ended until the queue returned to its "
        "pre-spike depth (None = never recovered during the run)"
    )

    # Capacity
    throughput: float = Field(description="Completed events per simulated second")
    utilization: float = Field(description="Fraction of worker capacity in use")

    timeseries: list[Sample]
