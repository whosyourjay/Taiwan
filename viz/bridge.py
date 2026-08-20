"""What a rank inside one exam is worth, and what it is worth in another.

Left: each exam's curve from its own takers onto the cohort, with the 五標 CEEC
publishes marked on 學測 so the axis has landmarks a reader already knows.
Right: the same curves read the other way, so a 學測 percentile can be traded for
the 統測 or 指考 percentile that buys the same seat.
"""

import sys

import numpy as np

from viz import common

NAME = "bridge.png"
GRID = 400
BASE = "gsat"
# 學測 percentiles to trade across, wide enough to cover where seats actually are.
TRADES = np.arange(10, 100, 5)


def invert(spline, level, grid):
    """The taker percentile at which `spline` reaches `level`, or None."""
    values = spline(grid)
    if level < values[0] or level > values[-1]:
        return None
    return float(np.interp(level, values, grid))


def draw_curves(panel, splines):
    grid = np.linspace(0.0, 1.0, GRID)
    for exam in sorted(splines):
        colour, label = common.style_of(exam)
        panel.plot(100 * grid, 100 * splines[exam](grid), color=colour,
                   linewidth=2.4, label=label)
    panel.plot([0, 100], [0, 100], color="#57606a", linewidth=1.0, linestyle="--",
               label="if percentiles transferred directly")
    for name, mark in common.BANDS:
        level = 100 * float(splines[BASE](mark / 100.0))
        panel.plot([mark, mark], [0, level], color="#1f6feb", linewidth=0.8,
                   alpha=0.45)
        panel.plot([mark], [level], "o", color="#1f6feb", markersize=4)
        panel.annotate(f"{name}\n{level:.0f}", xy=(mark, level), xytext=(3, -22),
                       textcoords="offset points", fontsize=8, color="#1f6feb")
    panel.set_xlabel("bottom % of that exam's takers")
    panel.set_ylabel("ability percentile within the age cohort")
    panel.set_title("Each exam's own curve, with the 學測 五標 marked")
    panel.legend(loc="upper left", frameon=False, fontsize=9)


def trades(splines):
    """For each 學測 percentile, the equal-ability percentile in every other exam."""
    grid = np.linspace(0.0, 1.0, GRID)
    out = {}
    for exam in sorted(splines):
        if exam == BASE:
            continue
        got = [(mark, invert(splines[exam], float(splines[BASE](mark / 100.0)), grid))
               for mark in TRADES]
        out[exam] = [(mark, 100 * value) for mark, value in got if value is not None]
    return out


def draw_trades(panel, splines):
    for exam, points in trades(splines).items():
        colour, label = common.style_of(exam)
        panel.plot([m for m, _ in points], [v for _, v in points], "o-",
                   color=colour, linewidth=2.0, markersize=4, label=label)
    panel.plot([0, 100], [0, 100], color="#57606a", linewidth=1.0, linestyle="--")
    for name, mark in common.BANDS:
        panel.axvline(mark, color="#1f6feb", linewidth=0.8, alpha=0.35)
        panel.annotate(name, xy=(mark, 2), fontsize=8, color="#1f6feb", rotation=90,
                       va="bottom", ha="right")
    panel.set_xlabel("bottom % of 學測 takers")
    panel.set_ylabel("bottom % of the other exam's takers, at equal ability")
    panel.set_title("The same seat, priced in another exam")
    panel.legend(loc="upper left", frameon=False, fontsize=9)


def draw(splines, name=NAME):
    figure, (left, right) = common.start(ncols=2, figsize=(14.5, 6.4))
    draw_curves(left, splines)
    draw_trades(right, splines)
    for panel in (left, right):
        panel.set_xlim(0, 100)
        panel.set_ylim(0, 100)
        panel.grid(alpha=0.18)
    return common.finish(figure, name,
                         "The bridge between exams, read off the department ranking")


def main():
    splines, _ = common.model()
    draw(splines)
    return 0


if __name__ == "__main__":
    sys.exit(main())
