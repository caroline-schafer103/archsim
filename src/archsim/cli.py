"""Command-line interface.

Architecture file (any number of stages):

    archsim run examples/video-upload.yaml
    archsim run examples/video-upload.yaml --vary transcode.workers=150,200,250

Quick single-stage runs with flags:

    archsim run --rate 10 --workers 5 10 20 --service-time 2 --duration 60
    archsim run ... --arrivals poisson --service exponential --seed 42
    archsim run ... --spike 120:60:3

Any run: --chart chart.png, --json results.json
"""

import argparse
import json
import random
import sys
from collections.abc import Callable
from pathlib import Path

from pydantic import ValidationError

from archsim.config import load_config, variations
from archsim.models import SimConfig, SimResults, Spike
from archsim.runner import compare

# Warn when more than this share of events never finished.
UNFINISHED_WARNING_THRESHOLD = 0.05

Row = tuple[str, Callable[[SimResults], object]]

SYSTEM_ROWS: list[Row] = [
    ("Generated", lambda r: r.generated),
    ("Completed", lambda r: r.completed),
    ("Still queued", lambda r: r.in_queue_at_end),
    ("In progress", lambda r: r.in_progress_at_end),
    ("Avg latency (s)", lambda r: r.avg_latency),
    ("P50 latency (s)", lambda r: r.p50_latency),
    ("P95 latency (s)", lambda r: r.p95_latency),
    ("P99 latency (s)", lambda r: r.p99_latency),
    ("Throughput (/s)", lambda r: r.throughput),
]


def _stage_rows(name: str) -> list[Row]:
    return [
        ("  Workers", lambda r: r.stage(name).workers),
        ("  Capacity (/s)", lambda r: r.stage(name).capacity),
        ("  Avg queue depth", lambda r: r.stage(name).avg_queue_depth),
        ("  Max queue depth", lambda r: r.stage(name).max_queue_depth),
        ("  Avg wait (s)", lambda r: r.stage(name).avg_wait_time),
        ("  Utilization", lambda r: r.stage(name).utilization),
    ]


def parse_spike(text: str) -> Spike:
    """Parse START:DURATION:MULTIPLIER, e.g. '120:60:3'."""
    try:
        start, duration, multiplier = (float(x) for x in text.split(":"))
        return Spike(start=start, duration=duration, multiplier=multiplier)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"invalid spike '{text}': expected START:DURATION:MULTIPLIER, e.g. 120:60:3"
        ) from e


def _fmt(value: object) -> str:
    if value is None:
        return "never"
    if isinstance(value, list):
        return ", ".join(_fmt(v) for v in value)
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def print_table(results: list[SimResults]) -> None:
    config = results[0].config
    sections: list[tuple[str | None, list[Row]]] = [(None, list(SYSTEM_ROWS))]
    if config.workload.spikes:
        sections[0][1].append(("Spike recovery (s)", lambda r: r.spike_recovery))
    for stage in config.stages:
        sections.append((f"[{stage.name}]", _stage_rows(stage.name)))
    if len(config.stages) > 1:
        sections.append((None, [("Bottleneck", lambda r: r.bottleneck.stage if r.bottleneck else "none")]))

    headers = [""] + [r.config.name for r in results]
    body: list[list[str] | str] = []
    for title, rows in sections:
        if title:
            body.append(title)
        body.extend([label] + [_fmt(get(r)) for r in results] for label, get in rows)

    table_rows = [row for row in body if isinstance(row, list)]
    widths = [max(len(row[i]) for row in [headers, *table_rows]) for i in range(len(headers))]

    def line(cells: list[str]) -> str:
        first = cells[0].ljust(widths[0])
        rest = [c.rjust(w) for c, w in zip(cells[1:], widths[1:])]
        return "  ".join([first, *rest])

    print(line(headers))
    print("-" * len(line(headers)))
    for row in body:
        print(row if isinstance(row, str) else line(row))


def print_notes(results: list[SimResults]) -> None:
    multi_stage = len(results[0].config.stages) > 1
    for r in results:
        b = r.bottleneck
        if multi_stage and b:
            print(
                f"\nBottleneck ({r.config.name}): {b.stage} is {b.utilization:.0%} busy "
                f"and accounts for {b.wait_share:.0%} of all time spent waiting in queues."
            )
        unfinished = r.generated - r.completed
        if r.generated and unfinished / r.generated > UNFINISHED_WARNING_THRESHOLD:
            print(
                f"\nWarning ({r.config.name}): {unfinished} of {r.generated} events never finished. "
                "Latency figures only cover completed events, so they understate the real delay."
            )


def print_summary(config: SimConfig, vary: str | None) -> None:
    w = config.workload
    pipeline = " -> ".join(s.name for s in config.stages)
    line = f"Arrivals: {w.rate:g}/s {w.arrivals}"
    if config.is_random:
        line += f" | Seed: {w.seed}"
    if len(config.stages) > 1:
        print(f"Pipeline: {pipeline}")
    if vary:
        print(f"Comparing: {vary.replace('=', ' = ')}")
    print(line)
    for s in w.spikes:
        print(f"Spike: {s.multiplier:g}x traffic from t={s.start:g}s to t={s.end:g}s")
    print()


def _configs_from_flags(args: argparse.Namespace, parser: argparse.ArgumentParser) -> list[SimConfig]:
    missing = [f for f in ("rate", "workers", "service_time", "duration") if getattr(args, f) is None]
    if missing:
        flags = ", ".join("--" + f.replace("_", "-") for f in missing)
        parser.error(f"give an architecture file, or all of: {flags}")
    return [
        SimConfig.single_stage(
            name=f"{w} workers",
            arrival_rate=args.rate,
            workers=w,
            service_time=args.service_time,
            duration=args.duration,
            arrivals=args.arrivals or "constant",
            service=args.service or "constant",
        )
        for w in args.workers
    ]


def _configs_from_file(args: argparse.Namespace, parser: argparse.ArgumentParser) -> list[SimConfig]:
    flag_only = [f for f in ("rate", "workers", "service_time", "duration", "arrivals", "service") if getattr(args, f)]
    if flag_only:
        flags = ", ".join("--" + f.replace("_", "-") for f in flag_only)
        parser.error(f"{flags} can't be combined with an architecture file; edit the file or use --vary")
    return variations(load_config(args.file), args.vary)


def build_configs(args: argparse.Namespace, parser: argparse.ArgumentParser) -> list[SimConfig]:
    if args.vary and not args.file:
        parser.error("--vary needs an architecture file (with flags, list several --workers instead)")
    configs = _configs_from_file(args, parser) if args.file else _configs_from_flags(args, parser)

    # Command-line overrides, then one shared seed so every configuration
    # sees the same arrival stream.
    workload_updates: dict = {}
    if args.spike:
        workload_updates["spikes"] = args.spike
    if args.seed is not None:
        workload_updates["seed"] = args.seed
    elif any(c.is_random and c.workload.seed is None for c in configs):
        workload_updates["seed"] = random.randrange(2**31)
    return [
        c.model_copy(update={"workload": c.workload.model_copy(update=workload_updates)}) for c in configs
    ]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="archsim", description="Event-driven architecture simulator")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="Simulate an architecture")
    p.add_argument("file", type=Path, nargs="?", help="Architecture YAML file (see examples/)")
    p.add_argument(
        "--vary",
        metavar="STAGE.FIELD=V1,V2,...",
        help="Compare variations of a file, e.g. transcode.workers=150,200,250 or workload.rate=2,3",
    )

    quick = p.add_argument_group("single-stage runs without a file")
    quick.add_argument("--rate", type=float, help="Arrivals per second")
    quick.add_argument("--workers", type=int, nargs="+", help="One or more worker counts to compare")
    quick.add_argument("--service-time", type=float, help="Seconds per event")
    quick.add_argument("--duration", type=float, help="Simulated seconds")
    quick.add_argument(
        "--arrivals", choices=["constant", "poisson"], help="constant: evenly spaced (default); poisson: random"
    )
    quick.add_argument(
        "--service", choices=["constant", "exponential"], help="constant (default) or exponential: random"
    )

    common = p.add_argument_group("any run")
    common.add_argument("--seed", type=int, help="Random seed for reproducible runs")
    common.add_argument(
        "--spike",
        type=parse_spike,
        action="append",
        default=[],
        metavar="START:DURATION:MULTIPLIER",
        help="Traffic spike, e.g. 120:60:3 = 3x traffic from t=120s for 60s (repeatable; replaces file spikes)",
    )
    common.add_argument("--json", type=Path, help="Write full results (incl. timeseries) to this file")
    common.add_argument("--chart", type=Path, help="Save a queue-depth chart (.png or .svg)")

    s = sub.add_parser("serve", help="Start the web UI and API")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--reload", action="store_true", help="Restart on code changes (development)")

    args = parser.parse_args(argv)

    if args.command == "serve":
        import uvicorn

        print(f"ArchSim running at http://{args.host}:{args.port}")
        uvicorn.run("archsim.api:app", host=args.host, port=args.port, reload=args.reload)
        return

    try:
        configs = build_configs(args, parser)
    except (ValidationError, ValueError, KeyError, OSError) as e:
        sys.exit(f"archsim: error: {e}")

    results = compare(configs)

    print_summary(results[0].config, args.vary)
    print_table(results)
    print_notes(results)

    if args.json:
        args.json.write_text(json.dumps([r.model_dump() for r in results], indent=2))
        print(f"\nWrote {args.json}")

    if args.chart:
        from archsim.charts import plot_queue_depth  # lazy: matplotlib is slow to import

        plot_queue_depth(results, args.chart)
        print(f"\nWrote {args.chart}")


if __name__ == "__main__":
    main()
