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
STAR = "star"


def curves():
    """The ability curves, bootstrapped from the first-pass ranking."""
    rows, _ = pool_fit.observations()
    order, schools = tiling.ranked()
    filled = tiling.admitted(pool_fit.YEAR)
    groups = tiling.grouped()
    scales = tiling.path_scales(
        tiling.placed_rows(rows, order, schools, groups), filled)
    placed = tiling.seats_in_order(rows, order, schools, groups, scales)
    points, _ = tiling.tile(placed, tiling.cohort_size(pool_fit.YEAR, filled=filled))
    return rows, tiling.splines(points)


def held(spline, bottom):
    """Where a share of one exam's takers lands, held inside the pool."""
    return float(np.clip(spline(bottom), 0.0, 1.0))


def star_level(row, splines):
    """繁星 quotes two floors: a 學測 gate and a rank inside the admittee's school.

    A class rank already counts students, so under the assumption that schools
    are alike it reads as an ability with no curve at all. The 學測 gate needs
    one. Both are floors rather than the margin, so take whichever binds harder.
    This is the naive reading of the pair, and wants replacing.
    """
    seen = []
    if row.get("class_pct") is not None:
        seen.append(float(row["class_pct"]) / 100.0)
    gates = row.get("xuece_gates") or {}
    if gates and "gsat" in splines:
        seen.append(held(splines["gsat"], max(gates.values()) / 100.0))
    return max(seen) if seen else None


def levels(row, splines):
    """Every ability a row's thresholds imply, tagged by what produced each."""
    exam = pool_fit.exam_of(row)
    if exam is None:
        return []
    if row["path"] == "star":
        level = star_level(row, splines)
        return [] if level is None else [(STAR, level)]
    top = pool_fit.top_of(row) if exam in splines else None
    return [] if top is None else [(exam, held(splines[exam], 1.0 - top))]


def read(rows, splines):
    """Turn every readable threshold into an ability, through its own curve."""
    return [(row, exam, level, float(row["seats"]))
            for row in rows for exam, level in levels(row, splines)]


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
    scored = read(rows, splines)
    exams = sorted({exam for _, exam, _, _ in scored})
    report(scored, exams, rows)
    print()
    for name, columns in LEVELS:
        written = tsvio.write_rows(ranking_path(name), table(scored, columns, exams))
        print(f"{written:>5} rows -> {name}")


if __name__ == "__main__":
    main()
