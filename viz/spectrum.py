"""The whole system on one axis: every seat placed at the ability it demands.

Ability runs over the age cohort, so the empty stretch at the left is the share
of the year group that no seat in the data accounts for. The two university
systems barely overlap, which is the shape worth seeing.
"""

import collections
import sys

import numpy as np

from viz import common

NAME = "spectrum.png"
BINS = 100
# Cumulative seat counts to name a department at, read from the top down, each
# with the label offset that keeps it off the curve and off its neighbours.
MILESTONES = ((500, 22), (5_000, -34), (25_000, -30), (75_000, 30))


def departments():
    """``(ability, seats, system)`` for every department the model scores."""
    out = []
    for (school, dept), seen in common.by_department().items():
        weight = sum(seats for _, seats in seen.values())
        level = sum(l * s for l, s in seen.values()) / weight
        out.append((100 * level, weight, common.system_of(seen), school, dept))
    out.sort(key=lambda item: -item[0])
    return out


def histogram(placed):
    """Seats per ability point, one row per system."""
    edges = np.linspace(0.0, 100.0, BINS + 1)
    stacks = collections.defaultdict(lambda: np.zeros(BINS))
    for level, seats, system, _, _ in placed:
        stacks[system][min(BINS - 1, int(level * BINS / 100))] += seats
    return edges, stacks


def draw_density(panel, placed):
    edges, stacks = histogram(placed)
    floor = np.zeros(BINS)
    width = 100.0 / BINS
    for system in ("general", "tech"):
        colour, label = common.SYSTEM[system]
        height = stacks[system] / width
        panel.bar(edges[:-1], height, width=width, bottom=floor, align="edge",
                  color=colour, alpha=0.85, linewidth=0,
                  label=f"{label}  ({stacks[system].sum():,.0f} seats)")
        floor = floor + height
    empty = next(i for i in range(BINS) if floor[i] > 0)
    panel.axvspan(0, edges[empty], color="#57606a", alpha=0.10, linewidth=0)
    panel.annotate(f"no seat in the data\nbelow ability {edges[empty]:.0f}",
                   xy=(edges[empty] / 2, floor.max() * 0.55), ha="center",
                   fontsize=9, color="#57606a")
    panel.set_ylabel("seats per ability point")
    panel.set_title("Where the seats are")
    panel.legend(loc="upper left", frameon=False, fontsize=9)


def draw_cumulative(panel, placed):
    levels = [level for level, *_ in placed]
    running = np.cumsum([seats for _, seats, *_ in placed])
    panel.plot(levels, running, color="#24292f", linewidth=1.8)
    panel.fill_between(levels, 1, running, color="#24292f", alpha=0.08)
    for target, dy in MILESTONES:
        if target > running[-1]:
            continue
        i = int(np.searchsorted(running, target))
        level, _, _, school, dept = placed[i]
        panel.plot([level], [running[i]], "o", color="#cf222e", markersize=5)
        panel.annotate(f"{target:,} seats — {school}{dept}",
                       xy=(level, running[i]), xytext=(-14, dy),
                       textcoords="offset points", fontsize=8.5, ha="right",
                       color="#24292f",
                       arrowprops={"arrowstyle": "-", "color": "#cf222e",
                                   "linewidth": 0.8})
    panel.set_yscale("log")
    panel.set_ylim(200, 2 * running[-1])
    panel.set_ylabel("seats at or above this ability")
    panel.set_title("What each rung of the ladder costs")


def draw(placed, name=NAME):
    figure, (top, bottom) = common.start(nrows=2, figsize=(13, 8.6), sharex=True)
    draw_density(top, placed)
    draw_cumulative(bottom, placed)
    for panel in (top, bottom):
        panel.set_xlim(0, 100)
        panel.grid(alpha=0.18)
    bottom.set_xlabel("ability percentile within the age cohort")
    return common.finish(
        figure, name,
        f"{len(placed):,} departments and {sum(s for _, s, *_ in placed):,.0f} seats"
        " with a readable bar, on one ability axis")


def main():
    draw(departments())
    return 0


if __name__ == "__main__":
    sys.exit(main())
