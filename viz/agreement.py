"""Do a department's own exams place it in the same spot?

A department admitting through two exams holds two readings of one margin. The
diagonal is what the model claims; the scatter around it is the error left in the
curves. This is the chart that tests the model rather than describing it.
"""

import collections
import itertools
import sys

import numpy as np

from viz import common

NAME = "agreement.png"
# Below this many shared departments a panel shows noise rather than a pattern.
MIN_SHARED = 25
PANELS = 5
BANDS = 10
# No department scores below this, so the lower corner is empty in every panel.
FRAME = (30, 100)


def pairs():
    """Every exam pair that scores enough departments, commonest first."""
    shared = collections.defaultdict(list)
    for key, seen in common.by_department().items():
        for left, right in itertools.combinations(sorted(seen), 2):
            shared[(left, right)].append((seen[left], seen[right], key))
    got = [(pair, rows) for pair, rows in shared.items() if len(rows) >= MIN_SHARED]
    got.sort(key=lambda item: -len(item[1]))
    return got[:PANELS]


def draw_pair(panel, pair, rows):
    left, right = pair
    x = np.array([100 * a for (a, _), _, _ in rows])
    y = np.array([100 * b for _, (b, _), _ in rows])
    size = [max(3.0, min(w, v) / 4) for (_, w), (_, v), _ in rows]
    panel.scatter(x, y, s=size, color=common.colour_of(right), alpha=0.35,
                  linewidths=0)
    panel.plot(FRAME, FRAME, color="#24292f", linewidth=1.0, linestyle="--")
    bias, spread = float(np.mean(y - x)), float(np.std(y - x))
    panel.set_xlabel(common.label_of(left))
    panel.set_ylabel(common.label_of(right))
    panel.set_title(f"{len(rows):,} departments\nbias {bias:+.1f}, spread {spread:.1f}",
                    fontsize=9.5)
    panel.set_xlim(*FRAME)
    panel.set_ylim(*FRAME)
    panel.grid(alpha=0.18)


def gaps_by_band(found):
    """Seat-weighted mean gap between paired readings, by ability decile."""
    bands = collections.defaultdict(list)
    for _, rows in found:
        for (a, wa), (b, wb), _ in rows:
            level = (a * wa + b * wb) / (wa + wb)
            bands[min(BANDS - 1, int(BANDS * level))].append((abs(a - b), wa + wb))
    out = []
    for band in range(BANDS):
        got = bands.get(band)
        if not got:
            out.append(0.0)
            continue
        gaps = np.array([g for g, _ in got])
        seats = np.array([s for _, s in got])
        out.append(100 * float(np.average(gaps, weights=seats)))
    return out


def draw_bands(panel, found):
    values = gaps_by_band(found)
    centres = [10 * band + 5 for band in range(BANDS)]
    panel.bar(centres, values, width=8.5, color="#8250df", alpha=0.8, linewidth=0)
    for centre, value in zip(centres, values):
        if value:
            panel.annotate(f"{value:.1f}", xy=(centre, value), xytext=(0, 3),
                           textcoords="offset points", ha="center", fontsize=8)
    panel.set_xlabel("ability percentile")
    panel.set_ylabel("gap between a department's own exams")
    panel.set_title("Where the readings disagree", fontsize=9.5)
    panel.set_xlim(0, 100)
    panel.grid(alpha=0.18, axis="y")


def draw(found, name=NAME):
    figure, panels = common.start(nrows=2, ncols=3, figsize=(15, 9))
    flat = panels.ravel()
    for panel, (pair, rows) in zip(flat, found):
        draw_pair(panel, pair, rows)
    draw_bands(flat[len(found)], found)
    for panel in flat[len(found) + 1:]:
        panel.axis("off")
    return common.finish(
        figure, name,
        "Two exams, one margin — how far apart they place the same department")


def main():
    found = pairs()
    if not found:
        print("no exam pair scores enough shared departments")
        return 1
    draw(found)
    return 0


if __name__ == "__main__":
    sys.exit(main())
