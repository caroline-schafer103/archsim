"""Static charts of simulation results (PNG/SVG via matplotlib)."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # file output only; no GUI window
import matplotlib.pyplot as plt  # noqa: E402

from archsim.models import SimResults  # noqa: E402

# Categorical slots in fixed order (validated for colorblind separation).
# Series beyond this many should be split into separate charts, not given new hues.
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#1f1f1e"
TEXT_SECONDARY = "#5f5e5a"
GRID = "#e4e3df"


def _label(r: SimResults) -> str:
    capacity = r.config.workers / r.config.service_time
    return f"{r.config.name} ({capacity:g}/s capacity)"


def plot_queue_depth(results: list[SimResults], path: Path) -> None:
    """Queue depth over time, one line per configuration."""
    if len(results) > len(SERIES_COLORS):
        raise ValueError(f"At most {len(SERIES_COLORS)} configurations per chart")

    fig, ax = plt.subplots(figsize=(9, 4.8), dpi=150, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)

    end = max(r.config.duration for r in results)
    for r, color in zip(results, SERIES_COLORS):
        times = [s.time for s in r.timeseries]
        depths = [s.queue_depth for s in r.timeseries]
        # zorder/clip_on keep a line sitting at 0 visible on top of the axis.
        ax.step(times, depths, where="post", color=color, linewidth=2, label=_label(r), zorder=3, clip_on=False)
        # Direct label at the line's end so identity isn't color-only.
        ax.annotate(
            r.config.name,
            xy=(times[-1], depths[-1]),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
            color=TEXT_PRIMARY,
        )

    first = results[0].config
    title_kw = dict(transform=ax.transAxes, ha="left", va="bottom")
    ax.text(0, 1.10, "Queue depth over time", fontsize=13, color=TEXT_PRIMARY, fontweight="bold", **title_kw)
    ax.text(
        0,
        1.03,
        f"Arrivals: {first.arrival_rate:g}/s  ·  Processing: {first.service_time:g}s per event",
        fontsize=10,
        color=TEXT_SECONDARY,
        **title_kw,
    )
    ax.set_xlabel("Simulated time (s)", color=TEXT_SECONDARY)
    ax.set_ylabel("Events waiting in queue", color=TEXT_SECONDARY)
    ax.set_xlim(0, end * 1.08)  # room for end labels
    ax.set_ylim(bottom=0)

    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9)

    if len(results) > 1:
        ax.legend(frameon=False, fontsize=9, labelcolor=TEXT_PRIMARY, loc="upper left")

    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
