"""Static charts of simulation results (PNG/SVG via matplotlib)."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # file output only; no GUI window
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.axes import Axes  # noqa: E402

from archsim.models import SimResults  # noqa: E402

# Categorical slots in fixed order (validated for colorblind separation).
# Series beyond this many should be split into separate charts, not given new hues.
SERIES_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#1f1f1e"
TEXT_SECONDARY = "#5f5e5a"
GRID = "#e4e3df"
SPIKE_FILL = "#efeeea"

HEADER_INCHES = 0.85  # space above the plots for title + subtitle
LEGEND_INCHES = 0.35  # extra header space for the shared legend row


def _legend_label(r: SimResults) -> str:
    if len(r.stages) == 1:
        return f"{r.config.name} ({r.stages[0].capacity:g}/s capacity)"
    return r.config.name


def _subtitle(results: list[SimResults]) -> str:
    config = results[0].config
    w = config.workload
    parts = [f"Arrivals: {w.rate:g}/s ({w.arrivals})"]
    if len(config.stages) == 1:
        s = config.stages[0]
        parts.append(f"Processing: {s.service_time:g}s per event ({s.service})")
    if config.is_random:
        parts.append(f"Seed: {w.seed}")
    return "  ·  ".join(parts)


def _style(ax: Axes) -> None:
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY, labelsize=9)


def _end_labels(ax: Axes, ends: list[tuple[float, float, str]]) -> None:
    """Direct labels at line ends, only where they're unambiguous.

    Lines that finish close together get no label (the shared legend covers
    them); a stacked pile of labels can't be matched to its lines.
    """
    low, high = ax.get_ylim()
    min_gap = (high - low) * 0.06
    ordered = sorted(ends, key=lambda e: e[1])
    for i, (x, y, name) in enumerate(ordered):
        crowded_below = i > 0 and y - ordered[i - 1][1] < min_gap
        crowded_above = i < len(ordered) - 1 and ordered[i + 1][1] - y < min_gap
        if crowded_below or crowded_above:
            continue
        ax.annotate(
            name,
            xy=(x, y),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=9,
            color=TEXT_PRIMARY,
            annotation_clip=False,
        )


def plot_queue_depth(results: list[SimResults], path: Path) -> None:
    """Queue depth over time: one panel per stage, one line per configuration."""
    if len(results) > len(SERIES_COLORS):
        raise ValueError(f"At most {len(SERIES_COLORS)} configurations per chart")

    stage_names = [s.name for s in results[0].config.stages]
    multi_stage = len(stage_names) > 1
    has_legend = len(results) > 1
    header = HEADER_INCHES + (LEGEND_INCHES if has_legend else 0)
    height = header + (2.6 * len(stage_names) + 0.6 if multi_stage else 4.0)

    fig, axes = plt.subplots(
        len(stage_names), 1, figsize=(9, height), dpi=150, facecolor=SURFACE, sharex=True, sharey=True, squeeze=False
    )
    axes = axes[:, 0]
    end = max(r.config.workload.duration for r in results)
    spikes = results[0].config.workload.spikes

    for i, (ax, stage) in enumerate(zip(axes, stage_names)):
        _style(ax)

        # Shade spike windows so cause (more traffic) sits next to effect (backlog).
        for spike in spikes:
            ax.axvspan(spike.start, spike.end, color=SPIKE_FILL, zorder=0, linewidth=0)
            if i == 0:
                ax.text(
                    (spike.start + spike.end) / 2,
                    0.98,
                    f"{spike.multiplier:g}x traffic",
                    transform=ax.get_xaxis_transform(),
                    ha="center",
                    va="top",
                    fontsize=9,
                    color=TEXT_SECONDARY,
                )

        for r, color in zip(results, SERIES_COLORS):
            series = r.stage(stage).timeseries
            # zorder/clip_on keep a line sitting at 0 visible on top of the axis.
            ax.step(
                [s.time for s in series],
                [s.queue_depth for s in series],
                where="post",
                color=color,
                linewidth=2 if not multi_stage else 1.6,
                label=_legend_label(r),
                zorder=3,
                clip_on=False,
            )

        if multi_stage:
            spec = results[0].config.stage(stage)
            # Say whether this stage changes between runs, so it's clear what
            # each legend entry means for this panel.
            worker_counts = {r.config.stage(stage).workers for r in results}
            workers = (
                "workers vary by run" if len(worker_counts) > 1 else f"{spec.workers} workers in every run"
                if len(results) > 1 else f"{spec.workers} workers"
            )
            ax.set_title(
                f"{stage}  ·  {workers}  ·  {spec.service_time:g}s per event",
                loc="left",
                fontsize=10,
                color=TEXT_PRIMARY,
                fontweight="bold",
            )
        ax.set_ylabel("Events waiting" if multi_stage else "Events waiting in queue", color=TEXT_SECONDARY)

    axes[0].set_ylim(bottom=0)
    axes[0].set_xlim(0, end * 1.1)  # room for end labels
    for ax, stage in zip(axes, stage_names):
        _end_labels(
            ax, [(r.stage(stage).timeseries[-1].time, r.stage(stage).timeseries[-1].queue_depth, r.config.name)
                 for r in results]
        )
    axes[-1].set_xlabel("Simulated time (s)", color=TEXT_SECONDARY)

    # Reserve a fixed band at the top for the title, aligned with the plot edge.
    fig.tight_layout(rect=(0, 0, 1, 1 - header / height), h_pad=1.6)
    left = axes[0].get_position().x0
    title = "Queue depth over time" + (" by stage" if multi_stage else "")
    fig.text(left, 1 - 0.3 / height, title, fontsize=13, color=TEXT_PRIMARY, fontweight="bold", va="center")
    fig.text(left, 1 - 0.62 / height, _subtitle(results), fontsize=10, color=TEXT_SECONDARY, va="center")

    # One legend for every panel, in the header, in series order.
    if has_legend:
        handles, labels = axes[0].get_legend_handles_labels()
        fig.legend(
            handles,
            labels,
            loc="center left",
            bbox_to_anchor=(left - 0.008, 1 - (HEADER_INCHES + LEGEND_INCHES / 2 - 0.05) / height),
            ncol=len(labels),
            frameon=False,
            fontsize=9,
            labelcolor=TEXT_PRIMARY,
            handlelength=1.6,
            columnspacing=1.6,
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)
