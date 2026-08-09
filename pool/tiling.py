"""Read each exam's curve off the department ranking instead of fitting it.

Every admit takes one seat, so walking the ranking from the best department down
and adding up seats says where a department's admits sit in the admitted pool.
Its published cutoff already says where its marginal admit sits among its own
exam's takers. The two together are one point on that exam's curve, and the seat
tables hold thousands of them.

This needs no density to be fitted and nothing can slide along the axis, because
the total seat count fixes the scale. What it needs instead is the ranking, and
seats for every path — a path we hold no seats for leaves a gap that the rest of
the tiling silently absorbs.
"""

import collections
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

import rank_uac
from lib import tsvio
from lib.paths import path
from pool import fit as pool_fit

RANKING = "rank-departments.tsv"


def ranked(source=RANKING):
    """Score for every ranked department, and a fallback score per school.

    A department the ranking never scored sits at its school's average, which
    is far closer than dropping it. Only the ordering matters here, and it is
    stable enough that a department landing a little out of place moves nothing.
    """
    order, schools = {}, collections.defaultdict(list)
    for row in tsvio.read_rows(path(source)):
        rank_uac.identify_department(row)
        score = float(row["score"])
        order[(row["school"], row["dept"])] = score
        schools[row["school"]].append(score)
    return order, {name: sum(got) / len(got) for name, got in schools.items()}


def seats_in_order(rows, order, schools):
    """Department-paths from the best department down, with their bars.

    A seat occupies ability whether or not its bar can be read, so 繁星 belongs
    here even though its cutoff is a rank inside one school.
    """
    out = []
    for row in rows:
        exam = pool_fit.exam_of(row)
        key = (row["school"], row["dept"])
        score = order.get(key, schools.get(row["school"]))
        if exam is None or score is None:
            continue
        out.append((score, exam, pool_fit.top_of(row), float(row["seats"])))
    out.sort(key=lambda item: -item[0])
    return out


def tile(placed, total=None):
    """Give each department-path the ability of its lowest admit.

    `total` is how many seats the pool really holds. Left out, the seats in hand
    are taken to be all of them, which reads every ability as if the paths we are
    missing did not exist.
    """
    total = float(total or sum(seats for *_, seats in placed))
    points = collections.defaultdict(list)
    above = 0.0
    for _, exam, top, seats in placed:
        above += seats
        if top is not None:
            points[exam].append((top, 1.0 - above / total, seats))
    return {exam: sorted(got) for exam, got in points.items()}, total


def ability(points, exam, tops):
    """Where a top fraction of one exam's takers lands in the admitted pool."""
    got = points[exam]
    return np.interp(tops, [top for top, _, _ in got],
                     [level for _, level, _ in got])


def scatter(points, exam, bands=10):
    """Seat-weighted spread of ability inside each band of top-of-takers.

    Several departments quoting the same bar should land at the same ability.
    How far apart they land is the noise in reading a curve off the ranking.
    """
    got = points[exam]
    out = []
    for low in np.arange(0.0, 1.0, 1.0 / bands):
        band = [(a, s) for t, a, s in got if low <= t < low + 1.0 / bands]
        if len(band) < 2:
            out.append(float("nan"))
            continue
        weights = np.array([s for _, s in band])
        values = np.array([a for a, _ in band])
        mean = np.average(values, weights=weights)
        out.append(float(np.sqrt(np.average((values - mean) ** 2, weights=weights))))
    return out


def report(points, total, held):
    exams = sorted(points)
    print(f"\n{held:,.0f} seats tiled into a pool of {total:,.0f}")
    for exam in exams:
        print(f"  {exam:<8}{len(points[exam]):>6} curve points")
    print(f"\n{'top of takers':<16}" + "".join(f"{exam:>12}" for exam in exams))
    for target in (0.01, 0.05, 0.10, 0.25, 0.50):
        cells = "".join(f"{100 * ability(points, exam, target):>11.1f}%"
                        for exam in exams)
        print(f"top {100 * target:>4.0f}% of takers".ljust(16) + cells)
    print("\nspread of ability among departments quoting the same bar, by decile")
    for exam in exams:
        print(f"  {exam:<8}"
              + " ".join(f"{100 * s:5.1f}" for s in scatter(points, exam)))


def main():
    rows, _ = pool_fit.observations()
    order, schools = ranked()
    placed = seats_in_order(rows, order, schools)
    held = sum(seats for *_, seats in placed)
    points, total = tile(placed)
    report(points, total, held)


if __name__ == "__main__":
    main()
