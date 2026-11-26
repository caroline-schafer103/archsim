"""Builds an architecture from a config, runs it, and summarizes the results.

This is the seam between the public models and the engine. The engine knows
nothing about configs; this module wires components together and turns raw
measurements into `SimResults`.
"""

import random
from dataclasses import dataclass
from statistics import fmean

from archsim.engine import (
    Constant,
    Distribution,
    Exponential,
    Queue,
    RateSchedule,
    RateWindow,
    Receiver,
    Recorder,
    Simulation,
    Sink,
    Source,
    WorkerPool,
    percentile,
    recovery_time,
)
from archsim.models import Bottleneck, Sample, SimConfig, SimResults, Stage, StageResults


def _mean(values: list[float]) -> float:
    return fmean(values) if values else 0.0


def _distribution(pattern: str, mean: float) -> Distribution:
    return Constant(mean) if pattern == "constant" else Exponential(mean)


def _samples(recorder: Recorder) -> list[Sample]:
    return [Sample(time=t, queue_depth=d, busy_workers=b) for t, d, b in recorder.samples]


def _service_rng(seed: int | None, index: int) -> random.Random:
    # Stage 0 keeps the original stream name so single-stage results stay
    # identical to earlier versions for the same seed.
    suffix = "" if index == 0 else f"-{index}"
    return random.Random(f"{seed}-service{suffix}")


@dataclass
class _BuiltStage:
    spec: Stage
    queue: Queue
    pool: WorkerPool
    recorder: Recorder


def run(config: SimConfig) -> SimResults:
    workload = config.workload

    # Pin a seed so every run is reproducible, even if the user didn't pick one.
    if workload.seed is None and config.is_random:
        workload = workload.model_copy(update={"seed": random.randrange(2**31)})
        config = config.model_copy(update={"workload": workload})

    sim = Simulation()
    sink = Sink(sim)

    # Build stages back to front so each knows where to send finished work.
    built: list[_BuiltStage] = []
    downstream: Receiver = sink
    for index in reversed(range(len(config.stages))):
        spec = config.stages[index]
        queue = Queue(sim, spec.name)
        pool = WorkerPool(
            sim,
            queue,
            spec.workers,
            _distribution(spec.service, spec.service_time),
            _service_rng(workload.seed, index),
            downstream=downstream,
        )
        built.insert(0, _BuiltStage(spec, queue, pool, Recorder(sim, [queue], [pool])))
        downstream = queue

    system = Recorder(sim, [b.queue for b in built], [b.pool for b in built])

    # Arrivals use their own stream, so every config with the same seed sees
    # the same traffic, and comparisons are apples-to-apples.
    source = Source(
        sim,
        RateSchedule(workload.rate, [RateWindow(s.start, s.end, s.multiplier) for s in workload.spikes]),
        gap_for=lambda mean: _distribution(workload.arrivals, mean),
        rng=random.Random(f"{workload.seed}-arrivals"),
        target=built[0].queue,
    )

    source.start()
    sim.run(until=workload.duration)
    for b in built:
        b.recorder.finish(workload.duration)
    system.finish(workload.duration)

    stages = [_stage_results(b, workload.duration) for b in built]
    done = sink.completed
    latencies = [j.latency for j in done]

    return SimResults(
        config=config,
        generated=len(source.generated),
        completed=len(done),
        in_queue_at_end=sum(s.in_queue_at_end for s in stages),
        in_progress_at_end=sum(s.in_progress_at_end for s in stages),
        avg_queue_depth=system.queue_area / workload.duration,
        max_queue_depth=system.max_queue_depth,
        avg_wait_time=_mean([j.total_wait for j in done]),
        avg_processing_time=_mean([j.total_processing for j in done]),
        avg_latency=_mean(latencies),
        p50_latency=percentile(latencies, 50),
        p95_latency=percentile(latencies, 95),
        p99_latency=percentile(latencies, 99),
        throughput=len(done) / workload.duration,
        spike_recovery=[recovery_time(system.samples, s.start, s.end) for s in workload.spikes],
        stages=stages,
        bottleneck=_bottleneck(built, stages),
        timeseries=_samples(system),
    )


def _stage_results(b: _BuiltStage, duration: float) -> StageResults:
    visits = b.queue.visits
    return StageResults(
        name=b.spec.name,
        workers=b.spec.workers,
        capacity=b.spec.capacity,
        completed=sum(1 for v in visits if v.finished is not None),
        in_queue_at_end=len(b.queue),
        in_progress_at_end=b.pool.busy,
        avg_queue_depth=b.recorder.queue_area / duration,
        max_queue_depth=b.recorder.max_queue_depth,
        avg_wait_time=_mean([v.wait_time for v in visits if v.wait_time is not None]),
        avg_processing_time=_mean([v.processing_time for v in visits if v.processing_time is not None]),
        utilization=b.recorder.busy_area / (b.spec.workers * duration),
        timeseries=_samples(b.recorder),
    )


def _bottleneck(built: list[_BuiltStage], stages: list[StageResults]) -> Bottleneck | None:
    """The stage holding the most queued work over time.

    By Little's law, the time-weighted queue depth is proportional to the
    total time events spend waiting there, so this is where waiting happens.
    """
    areas = [b.recorder.queue_area for b in built]
    total = sum(areas)
    if total <= 1e-9:
        return None
    i = max(range(len(areas)), key=areas.__getitem__)
    return Bottleneck(stage=stages[i].name, utilization=stages[i].utilization, wait_share=areas[i] / total)


def compare(configs: list[SimConfig]) -> list[SimResults]:
    return [run(c) for c in configs]
