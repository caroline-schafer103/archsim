"""Builds an architecture from a config, runs it, and summarizes the results.

This is the seam between the public models and the engine. When we move from
a fixed pipeline to arbitrary graphs (Phase 2), only `_build` changes.
"""

from statistics import fmean

from archsim.engine import Queue, Recorder, Simulation, Sink, Source, WorkerPool
from archsim.models import Sample, SimConfig, SimResults


def _mean(values: list[float]) -> float:
    return fmean(values) if values else 0.0


def run(config: SimConfig) -> SimResults:
    sim = Simulation()
    sink = Sink()
    queue = Queue(sim)
    pool = WorkerPool(sim, queue, config.workers, config.service_time, downstream=sink)
    source = Source(sim, config.arrival_rate, target=queue)
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
