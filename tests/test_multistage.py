from pathlib import Path

import pytest
from pydantic import ValidationError

from archsim import SimConfig, run
from archsim.cli import main
from archsim.config import apply_vary, load_config, parse_vary, variations
from archsim.models import Stage, Workload

EXAMPLES = Path(__file__).parent.parent / "examples"


def pipeline(rate=10, duration=60, *stages: tuple[str, int, float]) -> SimConfig:
    return SimConfig(
        workload=Workload(rate=rate, duration=duration),
        stages=[Stage(name=n, workers=w, service_time=t) for n, w, t in stages],
    )


# --- Simulation ------------------------------------------------------------


def test_latency_is_sum_of_stages_when_nothing_waits():
    r = run(pipeline(1, 60, ("a", 5, 2), ("b", 5, 3)))
    assert r.avg_latency == pytest.approx(5.0)
    assert r.bottleneck is None
    assert [s.name for s in r.stages] == ["a", "b"]


def test_downstream_bottleneck_is_detected():
    # a: capacity 20/s (plenty). b: capacity 5/s with 10/s arriving -> backlog at b.
    r = run(pipeline(10, 60, ("a", 20, 1), ("b", 5, 1)))
    assert r.stage("a").max_queue_depth <= 1
    assert r.stage("b").max_queue_depth > 200
    assert r.bottleneck.stage == "b"
    assert r.bottleneck.wait_share == pytest.approx(1.0)
    assert r.throughput == pytest.approx(5, rel=0.05)


def test_upstream_bottleneck_shields_downstream():
    # a: 5/s capacity throttles the flow, so b (also 5/s) never queues.
    r = run(pipeline(10, 60, ("a", 5, 1), ("b", 5, 1)))
    assert r.bottleneck.stage == "a"
    assert r.stage("b").max_queue_depth <= 1


@pytest.mark.parametrize("workers", [1, 5, 50])
def test_jobs_are_conserved_across_stages(workers):
    r = run(pipeline(10, 60, ("a", workers, 1), ("b", 3, 1), ("c", workers, 0.5)))
    in_system = sum(s.in_queue_at_end + s.in_progress_at_end for s in r.stages)
    assert r.generated == r.completed + in_system
    assert r.stage("c").completed == r.completed


def test_stage_service_streams_are_independent_of_each_other():
    # Changing stage b must not change the arrival stream.
    config = load_config(EXAMPLES / "video-upload.yaml")
    a = run(apply_vary(config, "publish", "workers", "12"))
    b = run(apply_vary(config, "publish", "workers", "20"))
    assert a.generated == b.generated


# --- Config files and variations -------------------------------------------


def test_example_file_loads():
    config = load_config(EXAMPLES / "video-upload.yaml")
    assert [s.name for s in config.stages] == ["upload", "transcode", "publish"]
    assert config.workload.spikes[0].multiplier == 2


def test_unknown_keys_are_rejected():
    with pytest.raises(ValidationError):
        SimConfig.model_validate(
            {"workload": {"rate": 1, "duration": 1}, "stages": [{"name": "a", "workers": 1, "service_time": 1, "wrokers": 2}]}
        )


def test_duplicate_stage_names_are_rejected():
    with pytest.raises(ValidationError):
        pipeline(1, 1, ("a", 1, 1), ("a", 1, 1))


def test_vary_creates_one_config_per_value():
    config = pipeline(10, 60, ("a", 5, 1), ("b", 5, 1))
    configs = variations(config, "b.workers=5,10,20")
    assert [c.stage("b").workers for c in configs] == [5, 10, 20]
    assert [c.stage("a").workers for c in configs] == [5, 5, 5]
    assert configs[0].name == "5 b workers"


def test_vary_workload_rate():
    configs = variations(pipeline(10, 60, ("a", 5, 1)), "workload.rate=5,15")
    assert [c.workload.rate for c in configs] == [5, 15]


@pytest.mark.parametrize("bad", ["workers=5", "a.name=x", "workload.seed=1"])
def test_vary_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        parse_vary(bad)


def test_vary_unknown_stage():
    with pytest.raises(KeyError):
        apply_vary(pipeline(10, 60, ("a", 5, 1)), "nope", "workers", "5")


# --- CLI -------------------------------------------------------------------


def test_cli_runs_example_with_vary(capsys, tmp_path):
    main(["run", str(EXAMPLES / "video-upload.yaml"), "--vary", "transcode.workers=150,250",
          "--chart", str(tmp_path / "c.png")])
    out = capsys.readouterr().out
    assert "Pipeline: upload -> transcode -> publish" in out
    assert "[publish]" in out
    assert "Bottleneck" in out
    assert (tmp_path / "c.png").exists()


def test_cli_flag_mode_still_works(capsys):
    main(["run", "--rate", "10", "--workers", "5", "20", "--service-time", "2", "--duration", "60"])
    out = capsys.readouterr().out
    assert "5 workers" in out and "20 workers" in out


def test_cli_rejects_mixing_file_and_flags():
    with pytest.raises(SystemExit):
        main(["run", str(EXAMPLES / "video-upload.yaml"), "--rate", "5"])
