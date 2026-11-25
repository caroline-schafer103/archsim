"""Public data contract: what goes into a simulation and what comes out.

These are Pydantic models so the future API (FastAPI) and UI can reuse them
directly for validation and JSON serialization.
"""

from pydantic import BaseModel, Field


class SimConfig(BaseModel):
    """MVP pipeline: Source -> Queue -> WorkerPool -> Sink."""

    name: str = "baseline"
    arrival_rate: float = Field(gt=0, description="Events per second (constant)")
    workers: int = Field(ge=1, description="Number of parallel workers")
    service_time: float = Field(gt=0, description="Seconds to process one event")
    duration: float = Field(gt=0, description="Simulated seconds to run")


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

    # Capacity
    throughput: float = Field(description="Completed events per simulated second")
    utilization: float = Field(description="Fraction of worker capacity in use")

    timeseries: list[Sample]
