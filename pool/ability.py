"""Score every department by the ability its own thresholds imply.

A threshold is a percentile inside one exam, and the tiling curves say what that
is worth in ability. A department admitting through three exams therefore holds
three readings of one margin, and its score is their seat-weighted average. Ranks
build the curves and nothing else, so no rank survives into a score.
"""

import collections
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np

from lib import tsvio
from lib.paths import ranking_path
from pool import fit as pool_fit
from pool import tiling

LEVELS = (
    ("ability-universities.tsv", ("school",)),
    ("ability-departments.tsv", ("school", "dept")),
    ("ability-groups.tsv", ("school", "dept", "application_group")),
)


def curves():
    """The ability curves, bootstrapped from the first-pass ranking."""
    rows, _ = pool_fit.observations()
    order, schools = tiling.ranked()
    placed = tiling.seats_in_order(rows, order, schools, tiling.grouped())
    points, _ = tiling.tile(placed)
    return rows, tiling.splines(points)


def read(rows, splines):
    """Turn every readable threshold into an ability, through its exam's curve."""
    out = []
    for row in rows:
        exam = pool_fit.exam_of(row)
        top = pool_fit.top_of(row) if exam in splines else None
        if top is None:
            continue
        level = float(np.clip(splines[exam](1.0 - top), 0.0, 1.0))
        out.append((row, exam, level, float(row["seats"])))
    return out


def collect(scored, columns):
    """Seat-weighted ability for each key, kept per exam and over all of them."""
    moment = collections.defaultdict(lambda: collections.defaultdict(float))
    weight = collections.defaultdict(lambda: collections.defaultdict(float))
    for row, exam, level, seats in scored:
        key = tuple(row[column] for column in columns)
        for name in ("all", exam):
            moment[key][name] += level * seats
            weight[key][name] += seats
    return moment, weight


def table(scored, columns, exams):
    """One ranked row per key, at the seat-weighted ability of its thresholds."""
    moment, weight = collect(scored, columns)
    out = []
    for key, sums in moment.items():
        seen = [sums[exam] / weight[key][exam] for exam in exams if weight[key][exam]]
        row = {"rank": 0}
        row.update(zip(columns, key))
        row["ability"] = round(100 * sums["all"] / weight[key]["all"], 2)
        row["seats"] = round(weight[key]["all"], 1)
        row["exams"] = len(seen)
        # How far apart this department's own exams place it, which is the error
        # left in the curves rather than anything about the department.
        row["spread"] = round(100 * (max(seen) - min(seen)), 2) if len(seen) > 1 else ""
        for exam in exams:
            share = weight[key][exam]
            row[exam] = round(100 * sums[exam] / share, 2) if share else ""
        out.append(row)
    out.sort(key=lambda row: -row["ability"])
    for rank, row in enumerate(out, 1):
        row["rank"] = rank
    return out


def disagreement(scored, exams):
    """Seat-weighted gap between the exams scoring one department, by decile."""
    moment, weight = collect(scored, ("school", "dept"))
    bands = collections.defaultdict(list)
    for key, sums in moment.items():
        seen = [sums[exam] / weight[key][exam] for exam in exams if weight[key][exam]]
        if len(seen) > 1:
            level = sums["all"] / weight[key]["all"]
            bands[min(9, int(10 * level))].append((max(seen) - min(seen),
                                                   weight[key]["all"]))
    out = []
    for band in range(10):
        got = bands.get(band)
        if not got:
            out.append(float("nan"))
            continue
        gaps = np.array([gap for gap, _ in got])
        seats = np.array([seat for _, seat in got])
        out.append(float(np.average(gaps, weights=seats)))
    return out


def report(scored, exams, rows):
    counted = collections.Counter()
    for row, exam, _, seats in scored:
        counted[exam] += seats
    missed = sum(float(row["seats"]) for row in rows
                 if pool_fit.exam_of(row) is not None) - sum(counted.values())
    print(f"\n{sum(counted.values()):,.0f} seats scored from their own threshold,"
          f" {missed:,.0f} with no readable bar")
    for exam in exams:
        print(f"  {exam:<8}{counted[exam]:>10,.0f} seats")
    print("\nhow far apart a department's own exams place it, by ability decile")
    print("  " + " ".join(f"{100 * gap:5.1f}" for gap in disagreement(scored, exams)))


def main():
    rows, splines = curves()
    exams = sorted(splines)
    scored = read(rows, splines)
    report(scored, exams, rows)
    print()
    for name, columns in LEVELS:
        written = tsvio.write_rows(ranking_path(name), table(scored, columns, exams))
        print(f"{written:>5} rows -> {name}")


if __name__ == "__main__":
    main()
