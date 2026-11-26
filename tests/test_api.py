from fastapi.testclient import TestClient

from archsim.api import app, resample
from archsim.models import Sample

client = TestClient(app)

TWO_STAGE = {
    "workload": {"rate": 10, "duration": 60, "arrivals": "poisson", "seed": 1},
    "stages": [
        {"name": "a", "workers": 20, "service_time": 1},
        {"name": "b", "workers": 5, "service_time": 1},
    ],
}


def test_examples_are_listed():
    examples = client.get("/api/examples").json()
    ids = {e["id"] for e in examples}
    assert {"video-upload", "email-notifications"} <= ids
    video = next(e for e in examples if e["id"] == "video-upload")
    assert video["title"] == "Video upload pipeline"
    assert "YouTube" in video["description"]


def test_simulate_returns_results():
    res = client.post("/api/simulate", json={"config": TWO_STAGE})
    assert res.status_code == 200
    [r] = res.json()["results"]
    assert r["bottleneck"]["stage"] == "b"
    assert len(r["stages"][0]["timeseries"]) == 601  # resampled for charts


def test_simulate_with_vary():
    res = client.post("/api/simulate", json={"config": TWO_STAGE, "vary": "b.workers=5,10,20"})
    results = res.json()["results"]
    assert [r["stages"][1]["workers"] for r in results] == [5, 10, 20]
    assert len({r["generated"] for r in results}) == 1  # same arrival stream


def test_random_runs_share_a_seed():
    config = {**TWO_STAGE, "workload": {**TWO_STAGE["workload"], "seed": None}}
    results = client.post("/api/simulate", json={"config": config, "vary": "b.workers=5,10"}).json()["results"]
    seeds = {r["config"]["workload"]["seed"] for r in results}
    assert len(seeds) == 1 and None not in seeds


def test_invalid_config_is_rejected():
    bad = {**TWO_STAGE, "stages": [{"name": "a", "workers": 0, "service_time": 1}]}
    assert client.post("/api/simulate", json={"config": bad}).status_code == 422


def test_bad_vary_is_rejected():
    res = client.post("/api/simulate", json={"config": TWO_STAGE, "vary": "nope.workers=1"})
    assert res.status_code == 400
    assert "nope" in res.json()["detail"]


def test_oversized_request_is_rejected():
    big = {**TWO_STAGE, "workload": {"rate": 10_000, "duration": 3600}}
    assert client.post("/api/simulate", json={"config": big}).status_code == 400


def test_resample_keeps_peaks():
    samples = [Sample(time=0, queue_depth=0, busy_workers=0),
               Sample(time=1.01, queue_depth=50, busy_workers=1),
               Sample(time=1.02, queue_depth=0, busy_workers=1)]
    out = resample(samples, duration=10, points=10)
    assert len(out) == 11
    assert max(s.queue_depth for s in out) == 50  # the brief spike survives
    assert out[-1].queue_depth == 0
