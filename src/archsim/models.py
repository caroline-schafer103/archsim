"""Public data contract: what goes into a simulation and what comes out.

These are Pydantic models so config files, the future API (FastAPI) and UI
can all reuse them directly for validation and JSON serialization. The shape
of `SimConfig` is exactly the shape of an architecture YAML file.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ArrivalPattern = Literal["constant", "poisson"]
ServicePattern = Literal["constant", "exponential"]


class _Strict(BaseModel):
    # Reject unknown keys so typos in config files fail loudly.
    model_config = ConfigDict(extra="forbid")


class Spike(_Strict):
    """A period of increased (or reduced) traffic."""

    start: float = Field(ge=0, description="Seconds into the simulation")
    duration: float = Field(gt=0, description="Seconds the spike lasts")
    multiplier: float = Field(gt=0, description="Arrival rate multiplier, e.g. 3 = triple traffic")

    @property
    def end(self) -> float:
        return self.start + self.duration


class Workload(_Strict):
    """What arrives at the system, and for how long we simulate."""

    rate: float = Field(gt=0, description="Average events per second")
    duration: float = Field(gt=0, description="Simulated seconds to run")
    arrivals: ArrivalPattern = Field(
        "constant", description="constant: evenly spaced; poisson: random, independent arrivals"
    )
    seed: int | None = Field(None, description="Random seed; same seed gives identical runs")
    spikes: list[Spike] = Field(default_factory=list, description="Traffic spikes during the run")


class Stage(_Strict):
    """A queue plus a pool of workers that process its events."""

    name: str = Field(pattern=r"^[A-Za-z0-9_-]+$")
    workers: int = Field(ge=1, description="Number of parallel workers")
    service_time: float = Field(gt=0, description="Average seconds to process one event")
    service: ServicePattern = Field(
        "constant", description="constant: every event takes service_time; exponential: random around it"
    )

    @property
    def capacity(self) -> float:
        """Events per second this stage can process when fully busy."""
        return self.workers / self.service_time


class SimConfig(_Strict):
    """An architecture: a workload flowing through stages in order."""

    name: str = "baseline"
    workload: Workload
    stages: list[Stage] = Field(min_length=1)

    @field_validator("stages")
    @classmethod
    def _unique_stage_names(cls, stages: list[Stage]) -> list[Stage]:
        names = [s.name for s in stages]
        if len(names) != len(set(names)):
            raise ValueError(f"stage names must be unique, got {names}")
        return stages

    @property
    def is_random(self) -> bool:
        return self.workload.arrivals != "constant" or any(s.service != "constant" for s in self.stages)

    def stage(self, name: str) -> Stage:
        for s in self.stages:
            if s.name == name:
                return s
        raise KeyError(f"no stage named '{name}' (stages: {', '.join(s.name for s in self.stages)})")

    @classmethod
    def single_stage(
        cls,
        *,
        arrival_rate: float,
        workers: int,
        service_time: float,
        duration: float,
        arrivals: ArrivalPattern = "constant",
        service: ServicePattern = "constant",
        seed: int | None = None,
        spikes: list[Spike] | None = None,
        name: str = "baseline",
    ) -> "SimConfig":
        """Shortcut for the classic Producer -> Queue -> Workers pipeline."""
        return cls(
            name=name,
            workload=Workload(
                rate=arrival_rate, duration=duration, arrivals=arrivals, seed=seed, spikes=spikes or []
            ),
            stages=[Stage(name="workers", workers=workers, service_time=service_time, service=service)],
        )


class Sample(BaseModel):
    """Queue and worker state at a moment in simulated time."""

    time: float
    queue_depth: int
    busy_workers: int


class StageResults(BaseModel):
    name: str
    workers: int
    capacity: float = Field(description="Events per second when fully busy")
    completed: int = Field(description="Events this stage finished processing")
    in_queue_at_end: int
    in_progress_at_end: int
    avg_queue_depth: float = Field(description="Time-weighted average")
    max_queue_depth: int
    avg_wait_time: float = Field(description="Queue wait at this stage, over events that started")
    avg_processing_time: float = Field(description="Over events this stage finished")
    utilization: float = Field(description="Fraction of worker capacity in use")
    timeseries: list[Sample]


class Bottleneck(BaseModel):
    stage: str
    utilization: float
    wait_share: float = Field(description="Fraction of all queueing time spent at this stage")


class SimResults(BaseModel):
    config: SimConfig

    # End-to-end counts
    generated: int
    completed: int = Field(description="Events that made it through every stage")
    in_queue_at_end: int = Field(description="Waiting in any stage's queue")
    in_progress_at_end: int = Field(description="Being processed at any stage")

    # System-wide queueing
    avg_queue_depth: float = Field(description="Time-weighted average, all queues combined")
    max_queue_depth: int = Field(description="All queues combined")

    # End-to-end timing (seconds), over completed events
    avg_wait_time: float = Field(description="Total time spent waiting in queues")
    avg_processing_time: float = Field(description="Total time being processed")
    avg_latency: float = Field(description="Arrival to completion")
    p50_latency: float
    p95_latency: float
    p99_latency: float

    throughput: float = Field(description="Completed events per simulated second")

    spike_recovery: list[float | None] = Field(
        description="Per spike: seconds after it ended until the total backlog returned to its "
        "pre-spike level (None = never recovered during the run)"
    )

    stages: list[StageResults]
    bottleneck: Bottleneck | None = Field(description="Stage where most queueing happens; None if nothing waited")

    timeseries: list[Sample] = Field(description="All stages combined")

    def stage(self, name: str) -> StageResults:
        return next(s for s in self.stages if s.name == name)
