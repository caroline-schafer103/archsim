from archsim import SimConfig, run
from archsim.charts import plot_queue_depth


def test_chart_is_written(tmp_path):
    results = [run(SimConfig(name=f"{w}w", arrival_rate=10, workers=w, service_time=2, duration=10)) for w in (5, 20)]
    out = tmp_path / "chart.png"
    plot_queue_depth(results, out)
    assert out.stat().st_size > 0
