"""Builds an architecture from a config, runs it, and summarizes the results.

This is the seam between the public models and the engine. When we move from
a fixed pipeline to arbitrary graphs (Phase 2), only `_build` changes.
"""

import random
from statistics import fmean

from archsim.engine import (
    Constant,
    Distribution,
    Exponential,
    Queue,
    Recorder,
    Simulation,
    Sink,
    Source,
    WorkerPool,
)
from archsim.models import Sample, SimConfig, SimResults


def _mean(values: list[float]) -> float:
    return fmean(values) if values else 0.0


def _distribution(pattern: str, mean: float) -> Distribution:
    return Constant(mean) if pattern == "constant" else Exponential(mean)


def run(config: SimConfig) -> SimResults:
    # Pin a seed so every run is reproducible, even if the user didn't pick one.
    if config.seed is None and config.is_random:
        config = config.model_copy(update={"seed": random.randrange(2**31)})

    # Separate streams: arrivals stay identical across configs with the same
    # seed (e.g. different worker counts), so comparisons are apples-to-apples.
    arrival_rng = random.Random(f"{config.seed}-arrivals")
    service_rng = random.Random(f"{config.seed}-service")

    sim = Simulation()
    sink = Sink()
    queue = Queue(sim)
    pool = WorkerPool(
        sim,
        queue,
        config.workers,
        _distribution(config.service, config.service_time),
        service_rng,
        downstream=sink,
    )
    source = Source(
        sim,
        _distribution(config.arrivals, 1 / config.arrival_rate),
        arrival_rng,
        target=queue,
    )
    recorder = Recorder(sim, queue, pool)

    source.start()
    sim.run(until=config.duration)
    recorder.finish(config.duration)

    started = [j for j in source.generated if j.start_time is not None]
    done = sink.completed

    return SimResults(
        config=config,
        generated=len(source.generated),
        completed=len(done),
        in_queue_at_end=len(queue),
        in_progress_at_end=pool.busy,
        avg_queue_depth=recorder.queue_area / config.duration,
        max_queue_depth=recorder.max_queue_depth,
        avg_wait_time=_mean([j.wait_time for j in started]),
        avg_processing_time=_mean([j.processing_time for j in done]),
        avg_latency=_mean([j.latency for j in done]),
        throughput=len(done) / config.duration,
        utilization=recorder.busy_area / (config.workers * config.duration),
        timeseries=[Sample(time=t, queue_depth=d, busy_workers=b) for t, d, b in recorder.samples],
    )


def compare(configs: list[SimConfig]) -> list[SimResults]:
    return [run(c) for c in configs]
