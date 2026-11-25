"""Command-line interface.

    archsim run --rate 10 --workers 5 --service-time 2 --duration 60
    archsim run --rate 10 --workers 5 10 20 --service-time 2 --duration 60
    archsim run ... --json results.json
"""

import argparse
import json
from pathlib import Path

from archsim.models import SimConfig, SimResults
from archsim.runner import compare

ROWS: list[tuple[str, str]] = [
    ("Workers", "config.workers"),
    ("Generated", "generated"),
    ("Completed", "completed"),
    ("Still queued", "in_queue_at_end"),
    ("In progress", "in_progress_at_end"),
    ("Avg queue depth", "avg_queue_depth"),
    ("Max queue depth", "max_queue_depth"),
    ("Avg wait (s)", "avg_wait_time"),
    ("Avg processing (s)", "avg_processing_time"),
    ("Avg latency (s)", "avg_latency"),
    ("Throughput (/s)", "throughput"),
    ("Utilization", "utilization"),
]


def _get(result: SimResults, path: str) -> object:
    obj: object = result
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def _fmt(value: object) -> str:
    return f"{value:.2f}" if isinstance(value, float) else str(value)


def print_table(results: list[SimResults]) -> None:
    headers = [""] + [r.config.name for r in results]
    rows = [[label] + [_fmt(_get(r, path)) for r in results] for label, path in ROWS]
    widths = [max(len(row[i]) for row in [headers, *rows]) for i in range(len(headers))]

    def line(cells: list[str]) -> str:
        first = cells[0].ljust(widths[0])
        rest = [c.rjust(w) for c, w in zip(cells[1:], widths[1:])]
        return "  ".join([first, *rest])

    print(line(headers))
    print("-" * len(line(headers)))
    for row in rows:
        print(line(row))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="archsim", description="Event-driven architecture simulator")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("run", help="Simulate Source -> Queue -> WorkerPool")
    p.add_argument("--rate", type=float, required=True, help="Arrivals per second")
    p.add_argument("--workers", type=int, nargs="+", required=True, help="One or more worker counts to compare")
    p.add_argument("--service-time", type=float, required=True, help="Seconds per event")
    p.add_argument("--duration", type=float, required=True, help="Simulated seconds")
    p.add_argument("--json", type=Path, help="Write full results (incl. timeseries) to this file")
    p.add_argument("--chart", type=Path, help="Save a queue-depth chart (.png or .svg)")

    args = parser.parse_args(argv)

    configs = [
        SimConfig(
            name=f"{w} workers",
            arrival_rate=args.rate,
            workers=w,
            service_time=args.service_time,
            duration=args.duration,
        )
        for w in args.workers
    ]
    results = compare(configs)
    print_table(results)

    if args.json:
        args.json.write_text(json.dumps([r.model_dump() for r in results], indent=2))
        print(f"\nWrote {args.json}")

    if args.chart:
        from archsim.charts import plot_queue_depth  # lazy: matplotlib is slow to import

        plot_queue_depth(results, args.chart)
        print(f"\nWrote {args.chart}")


if __name__ == "__main__":
    main()
