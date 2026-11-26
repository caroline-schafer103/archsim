"""HTTP API for the web UI.

    archsim serve              # http://localhost:8000

Reuses the same models and runner as the CLI: the request body is a
`SimConfig` (the same shape as an architecture YAML file).
"""

import random
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from archsim.config import load_config, variations
from archsim.models import Sample, SimConfig, SimResults
from archsim.runner import compare

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = ROOT / "examples"
WEB_DIST = ROOT / "web" / "dist"

MAX_RUNS = 8
MAX_EVENTS = 500_000  # expected arrivals across all runs; keeps requests fast
CHART_POINTS = 600  # timeseries are resampled to this many points per series


class SimulateRequest(BaseModel):
    config: SimConfig
    vary: str | None = Field(None, description="e.g. 'transcode.workers=150,200,250'")


class SimulateResponse(BaseModel):
    results: list[SimResults]


class Example(BaseModel):
    id: str
    title: str
    description: str
    config: SimConfig


app = FastAPI(title="ArchSim", description="Event-driven architecture simulator")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/examples")
def examples() -> list[Example]:
    out = []
    for path in sorted(EXAMPLES_DIR.glob("*.yaml")):
        config = load_config(path)
        title, description = _header_comment(path)
        out.append(Example(id=path.stem, title=title or config.name, description=description, config=config))
    return out


@app.post("/api/simulate")
def simulate(req: SimulateRequest) -> SimulateResponse:
    # Sync endpoint: FastAPI runs it in a worker thread, so a long simulation
    # doesn't block other requests.
    try:
        configs = variations(req.config, req.vary)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e).strip('"'))
    _check_limits(configs)

    # One shared seed, so every run sees the same arrival stream.
    if any(c.is_random and c.workload.seed is None for c in configs):
        seed = random.randrange(2**31)
        configs = [c.model_copy(update={"workload": c.workload.model_copy(update={"seed": seed})}) for c in configs]

    results = [_for_chart(r) for r in compare(configs)]
    return SimulateResponse(results=results)


def _check_limits(configs: list[SimConfig]) -> None:
    if len(configs) > MAX_RUNS:
        raise HTTPException(status_code=400, detail=f"at most {MAX_RUNS} variations per request")
    expected = 0.0
    for c in configs:
        w = c.workload
        peak = max([s.multiplier for s in w.spikes], default=1)
        expected += w.rate * w.duration * max(peak, 1)
    if expected > MAX_EVENTS:
        raise HTTPException(
            status_code=400,
            detail=f"that's ~{expected:,.0f} events; keep it under {MAX_EVENTS:,} (lower the rate or duration)",
        )


def resample(samples: list[Sample], duration: float, points: int = CHART_POINTS) -> list[Sample]:
    """Resample a step series onto an even time grid, keeping peaks.

    Each grid point carries the *maximum* queue depth seen since the previous
    point, so short spikes survive downsampling. Every series ends up on the
    same grid, which lets the UI line runs up point-for-point.
    """
    if not samples:
        return []
    grid = [duration * i / points for i in range(points + 1)]
    out: list[Sample] = []
    i = 0
    current = samples[0]
    for t in grid:
        peak_depth = current.queue_depth
        while i < len(samples) and samples[i].time <= t:
            current = samples[i]
            peak_depth = max(peak_depth, current.queue_depth)
            i += 1
        out.append(Sample(time=t, queue_depth=peak_depth, busy_workers=current.busy_workers))
    return out


def _for_chart(r: SimResults) -> SimResults:
    duration = r.config.workload.duration
    return r.model_copy(
        update={
            "timeseries": resample(r.timeseries, duration),
            "stages": [s.model_copy(update={"timeseries": resample(s.timeseries, duration)}) for s in r.stages],
        }
    )


def _header_comment(path: Path) -> tuple[str, str]:
    """Title and description from an example file's leading comment block."""
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        lines.append(line.lstrip("#").strip())
    title = lines[0] if lines else ""
    rest = []
    for line in lines[1:]:
        if not line:
            break
        rest.append(line)
    return title.rstrip(":"), " ".join(rest)


# Serve the built frontend (npm run build) from the same server.
if WEB_DIST.exists():
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
