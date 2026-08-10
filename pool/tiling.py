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
from scipy import interpolate

import rank_uac
from lib import tsvio
from lib.paths import ranking_path
from pool import fit as pool_fit

RANKING = "rank-departments.tsv"
GROUPS = "rank-application-groups.tsv"

# 分發 and 統測登記分發 publish a cutoff for every 系組, so each one can be placed
# on its own. 繁星 and 個申 publish one cutoff per department, and splitting their
# seats would scatter them along the axis under a bar that never moved.
PER_GROUP = ("uac", "tech")

# Places where the smoothed curve is pinned. Thousands of bars carry far less
# shape than that, and a consumer reading the curve pays for every one of them.
KNOTS = 10


def ranked(source=RANKING):
    """Score for every ranked department, and a fallback score per school.

    A department the ranking never scored sits at its school's average, which
    is far closer than dropping it. Only the ordering matters here, and it is
    stable enough that a department landing a little out of place moves nothing.
    """
    order, schools = {}, collections.defaultdict(list)
    for row in tsvio.read_rows(ranking_path(source)):
        rank_uac.identify_department(row)
        score = float(row["score"])
        order[(row["school"], row["dept"])] = score
        schools[row["school"]].append(score)
    return order, {name: sum(got) / len(got) for name, got in schools.items()}


def grouped(source=GROUPS):
    """Score for each 系組 the ranking placed separately from its department."""
    return {(row["school"], row["dept"], row["application_group"]): float(row["score"])
            for row in tsvio.read_rows(ranking_path(source))}


def seats_in_order(rows, order, schools, groups=None):
    """Department-paths from the best down, each at the finest rank it has.

    A seat occupies ability whether or not its bar can be read, so 繁星 belongs
    here even though its cutoff is a rank inside one school.
    """
    groups = groups or {}
    out = []
    for row in rows:
        exam = pool_fit.exam_of(row)
        key = (row["school"], row["dept"])
        score = order.get(key, schools.get(row["school"]))
        if row["path"] in PER_GROUP:
            score = groups.get((*key, row.get("application_group")), score)
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


def pooled(points):
    """Seat-weighted ability at each distinct bar, with the seats behind it."""
    weight = collections.defaultdict(float)
    moment = collections.defaultdict(float)
    for top, level, seats in points:
        weight[top] += seats
        moment[top] += seats * level
    tops = sorted(weight)
    return (np.array(tops), np.array([moment[t] / weight[t] for t in tops]),
            np.array([weight[t] for t in tops]))


def isotonic(levels, weights):
    """The closest non-increasing curve, in seat-weighted least squares.

    Reaching further down an exam's takers cannot reach a better student, so the
    curve has to fall. Where the points rise instead, the rise is noise, and
    pooling each rising run into its shared mean is what removes it.
    """
    blocks = []
    for level, weight in zip(levels, weights):
        blocks.append([level * weight, weight, 1])
        while len(blocks) > 1 and (blocks[-2][0] / blocks[-2][1]
                                   < blocks[-1][0] / blocks[-1][1]):
            moment, weight, count = blocks.pop()
            blocks[-1][0] += moment
            blocks[-1][1] += weight
            blocks[-1][2] += count
    return np.concatenate([np.full(count, moment / weight)
                           for moment, weight, count in blocks])


def curve(points):
    """One exam's bar-to-ability curve: distinct bars, pooled and made to fall."""
    tops, levels, weights = pooled(points)
    return tops, isotonic(levels, weights)


def knots(tops, levels, weights, count):
    """Thin the curve to `count` places, each carrying the same weight of seats.

    Seats rather than bars, so a stretch of the axis that many students actually
    sit in gets the detail, and a long tail of tiny departments does not.
    """
    if count >= len(tops):
        return np.array(tops), np.array(levels)
    carried = np.cumsum(weights)
    wanted = np.linspace(0.0, carried[-1], count)[1:]
    picked = sorted({0} | {int(np.searchsorted(carried, w)) for w in wanted})
    picked = [i for i in picked if i < len(tops)]
    return np.array(tops)[picked], np.array(levels)[picked]


def smooth(points, count=KNOTS):
    """A curve with a derivative, so it can be differentiated into a density.

    Isotonic output is a staircase, and the height of a step says nothing except
    that the fit ran out of evidence to separate its bars. A shape-preserving
    cubic through evenly weighted knots keeps the curve rising and gives it the
    smooth slope the density needs.
    """
    tops, levels, weights = pooled(points)
    fitted = isotonic(levels, weights)
    # Read from the bottom up, so both axes rise and the spline stays monotone.
    bottoms, rising = knots(1.0 - tops[::-1], fitted[::-1], weights[::-1], count)
    return interpolate.PchipInterpolator(bottoms, rising, extrapolate=True)


def carried_seats(placed, count=KNOTS):
    """Each exam's seats below an admit percentile, as a smooth rising curve.

    Walking the pool from the bottom up gives every exam a staircase of seats
    collected so far. Reading that staircase at evenly spaced percentiles is
    reading it at evenly spaced seats, since the axis counts seats.
    """
    order = list(reversed(placed))
    seats = np.array([s for *_, s in order])
    total = float(seats.sum())
    edges = np.concatenate([[0.0], np.cumsum(seats)]) / total
    picks = np.linspace(0.0, 1.0, count)
    out = {}
    for exam in sorted({name for _, name, _, _ in order}):
        mine = np.where(np.array([name == exam for _, name, _, _ in order]), seats, 0)
        carried = np.concatenate([[0.0], np.cumsum(mine)])
        out[exam] = interpolate.PchipInterpolator(
            picks, np.interp(picks, edges, carried)
        )
    return out, total


def seat_shares(placed, count=KNOTS, grid=400):
    """Which exam fills the pool at each ability, from the slope of those curves.

    Each admit holds one seat on one path, so the paths divide the pool between
    them and their shares add to one. Nothing here assumes who sat which exam — a
    student sitting two of them still holds a single seat, so the double counting
    that dogged the taker pools cannot arise.
    """
    fitted, total = carried_seats(placed, count)
    axis = np.linspace(0.0, 1.0, grid)
    rates = {exam: spline.derivative()(axis) for exam, spline in fitted.items()}
    stacked = sum(rates.values())
    return {exam: got / stacked for exam, got in rates.items()}, total


def curves(points):
    """Every exam's curve, built once so a caller can read it many times."""
    return {exam: curve(got) for exam, got in points.items()}


def splines(points, count=KNOTS):
    """Every exam's smoothed curve."""
    return {exam: smooth(got, count) for exam, got in points.items()}


def ability(fitted, tops):
    """Where a top fraction of one exam's takers lands in the admitted pool."""
    return np.interp(tops, *fitted)


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


def report(points, fitted, total, held):
    exams = sorted(points)
    print(f"\n{held:,.0f} seats tiled into a pool of {total:,.0f}")
    for exam in exams:
        print(f"  {exam:<8}{len(points[exam]):>6} bars,"
              f"{len(fitted[exam][0]):>6} distinct")
    print(f"\n{'top of takers':<16}" + "".join(f"{exam:>12}" for exam in exams))
    for target in (0.01, 0.05, 0.10, 0.25, 0.50, 0.75):
        cells = "".join(f"{100 * ability(fitted[exam], target):>11.1f}%"
                        for exam in exams)
        print(f"top {100 * target:>4.0f}% of takers".ljust(16) + cells)
    print("\nspread of ability among departments quoting the same bar, by decile")
    for exam in exams:
        print(f"  {exam:<8}"
              + " ".join(f"{100 * s:5.1f}" for s in scatter(points, exam)))


def main():
    rows, _ = pool_fit.observations()
    order, schools = ranked()
    placed = seats_in_order(rows, order, schools, grouped())
    held = sum(seats for *_, seats in placed)
    points, total = tile(placed)
    fitted = curves(points)
    report(points, fitted, total, held)
    shares, _ = seat_shares(placed)
    from pool.tiling_plot import draw

    print(f"\nwrote {draw(points, fitted, splines(points), shares, total)}")


if __name__ == "__main__":
    main()
