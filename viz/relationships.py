"""Draw the measurements that define the shared admission-rank component."""

import collections
import contextlib
import sys

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from lib.paths import figure_path  # noqa: E402
from rank import uac  # noqa: E402

OUT = figure_path("relationships.png")
FONTS = ["PingFang HK", "Heiti TC", "Arial Unicode MS", "Hiragino Sans GB"]


def component_observations(rows):
    """Rebuild the component inputs from scored pipeline rows."""
    extra = {path: [row for row in rows if row["path"] == path]
             for path in ("star", "star_eight", "apply")}
    return uac.component_observations(
        [row for row in rows if row["path"] == "uac"],
        [row for row in rows if row["path"] == "tech"],
        extra,
    )


def points_for(observations, model, variable):
    """Predict one measurement's component score from its companion paths."""
    grouped = collections.defaultdict(list)
    for observation in observations:
        grouped[observation[0]].append(observation)
    points = []
    for key, group in grouped.items():
        for _, candidate, value, seats in group:
            if candidate != variable:
                continue
            companions = [(other, observed) for _, other, observed, _ in group
                          if other != variable]
            if companions:
                points.append((key, value, seats, model.combine(companions)))
    return points


def point_sizes(points):
    """Seat weights that remain readable when a department is very large."""
    return np.clip(3.0 + 1.5 * np.sqrt([point[2] for point in points]), 5, 30)


def score_limits(model):
    """A common, padded factor-score range for every panel."""
    values = list(model.scores.values())
    span = max(values) - min(values)
    return min(values) - span * 0.06, max(values) + span * 0.06


def stats_text(stats):
    """Compact common annotation for the one-component fit."""
    return (
        f"one component; R²={stats['r2']:.2f}\n"
        f"cross-source CV={stats['cv_rmse']:.2f} SD"
    )


def measurement_panel(ax, points, model, stats, variable, title, xlabel, colour):
    """Panel wrapper that makes the plotted measurement explicit."""
    x = np.array([point[1] for point in points])
    y = np.array([point[3] for point in points])
    grid = np.linspace(0, 100, 300)
    ax.scatter(x, y, s=point_sizes(points), c=colour, alpha=0.30, edgecolors="none")
    ax.plot(grid, [model.predict(variable, value) for value in grid], color="#d1242f", lw=2.4)
    ax.set(xlim=(0, 100), ylim=score_limits(model), xlabel=xlabel,
           ylabel="component from other paths")
    ax.set_title(title, loc="left", fontweight="bold")
    ax.text(0.03, 0.96, stats_text(stats), transform=ax.transAxes, va="top", fontsize=9,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8})
    ax.grid(alpha=0.18)


def xuece_panel(ax, observations, model, stats):
    """Show the three subject-family offsets on their shared 學測 slope."""
    colours = {"language": "#1f6feb", "social": "#8250df", "stem": "#1a7f37"}
    grid = np.linspace(0, 100, 300)
    for family, colour in colours.items():
        variable = f"apply:{family}"
        points = points_for(observations, model, variable)
        if not points:
            continue
        ax.scatter(
            [point[1] for point in points], [point[3] for point in points],
            s=point_sizes(points), c=colour, alpha=0.30, edgecolors="none", label=family,
        )
        ax.plot(grid, [model.predict(variable, value) for value in grid], color=colour, lw=2.4)
    ax.set(xlim=(0, 100), ylim=score_limits(model), xlabel="學測 screen percentile",
           ylabel="component from other paths")
    ax.set_title("個人申請 學測 screen → component", loc="left", fontweight="bold")
    ax.text(0.03, 0.96, stats_text(stats), transform=ax.transAxes, va="top", fontsize=9,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8})
    ax.legend(title="subject family", loc="lower right", frameon=False, fontsize=8)
    ax.grid(alpha=0.18)


def star_points(observations, model):
    """The fitted 繁星 measurements, retaining a display-only strictest gate."""
    values = collections.defaultdict(dict)
    companions = collections.defaultdict(list)
    for key, variable, value, seats in observations:
        if variable.startswith("star:"):
            values[key][variable] = value, seats
        else:
            companions[key].append((variable, value))
    return [
        (
            model.combine([(variable, value) for variable, (value, _) in source.items()]),
            model.combine(companions[key]),
            source["star:class"][1],
            source["star:class"][0],
            max(value for variable, (value, _) in source.items()
                if variable.startswith("star:gate:")),
        )
        for key, source in values.items()
        if "star:class" in source and any(
            variable.startswith("star:gate:") for variable in source
        ) and companions[key]
    ]


def star_panel(ax, points, model, stats):
    """Compare the multi-input 繁星 estimate with its fitted department value."""
    x = np.array([point[0] for point in points])
    y = np.array([point[1] for point in points])
    ax.scatter(x, y, s=point_sizes(points), c=[point[4] for point in points], cmap="viridis",
               alpha=0.30, edgecolors="none")
    lo, hi = score_limits(model)
    ax.plot((lo, hi), (lo, hi), color="#d1242f", lw=2.4)
    ax.set(xlim=(lo, hi), ylim=(lo, hi), xlabel="class rank + gate component",
           ylabel="component from other paths")
    ax.set_title("繁星 measurements → component", loc="left", fontweight="bold")
    ax.text(0.03, 0.96, stats_text(stats), transform=ax.transAxes, va="top", fontsize=9,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8})
    ax.grid(alpha=0.18)


def star_gate_panel(ax, observations, model, stats):
    """Show the separate language, social, and STEM gate calibrations."""
    colours = {"language": "#1f6feb", "social": "#8250df", "stem": "#1a7f37"}
    grid = np.linspace(0, 100, 300)
    for family, colour in colours.items():
        variable = f"star:gate:{family}"
        points = points_for(observations, model, variable)
        if not points:
            continue
        ax.scatter(
            [point[1] for point in points], [point[3] for point in points],
            s=point_sizes(points), c=colour, alpha=0.30, edgecolors="none", label=family,
        )
        ax.plot(grid, [model.predict(variable, value) for value in grid], color=colour, lw=2.4)
    ax.set(xlim=(0, 100), ylim=score_limits(model), xlabel="學測 gate percentile",
           ylabel="component from other paths")
    ax.set_title("繁星 gates → component", loc="left", fontweight="bold")
    ax.text(0.03, 0.96, stats_text(stats), transform=ax.transAxes, va="top", fontsize=9,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.8})
    ax.legend(title="subject family", loc="lower right", frameon=False, fontsize=8)
    ax.grid(alpha=0.18)


def draw(rows, models, output=OUT):
    """Write the four-panel one-component diagnostic."""
    plt.rcParams["font.sans-serif"] = FONTS + plt.rcParams["font.sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    model, stats = models["component"]
    observations = component_observations(rows)
    figure, axes = plt.subplots(2, 2, figsize=(13, 10), constrained_layout=True)
    measurement_panel(
        axes[0, 0], points_for(observations, model, "tech"), model, stats, "tech",
        "統測 → component", "統測 cutoff order within its year", "#1a7f37",
    )
    xuece_panel(axes[0, 1], observations, model, stats)
    stars = star_points(observations, model)
    star_panel(axes[1, 0], stars, model, stats)
    star_gate_panel(axes[1, 1], observations, model, stats)
    figure.suptitle("One component across Taiwan admission measurements",
                     fontsize=14, fontweight="bold")
    figure.savefig(output, dpi=170)
    plt.close(figure)
    return output


def main():
    with contextlib.redirect_stdout(sys.stderr):
        rows, models = uac.build_rows(with_models=True)
    print(f"wrote {draw(rows, models)}")


if __name__ == "__main__":
    main()
