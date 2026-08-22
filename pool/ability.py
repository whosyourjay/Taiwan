"""Score every department by the ability its own thresholds imply.

A threshold is a percentile inside one exam, and the tiling curves say what that
is worth in ability. A department admitting through three exams therefore holds
three readings of one margin, and its score is their seat-weighted average. Ranks
build the curves and nothing else, so no rank survives into a score.
"""

import collections

if __package__ in (None, ""):
    import _bootstrap  # noqa: F401

import numpy as np

from lib import tsvio
from lib.english import english_names
from lib.paths import ranking_path
from pool import fit as pool_fit
from pool import tiling

LEVELS = (
    ("ability-universities.tsv", ("school",)),
    ("ability-departments.tsv", ("school", "dept")),
    ("ability-groups.tsv", ("school", "dept", "application_group")),
)
STAR = "star"
STAR_EIGHT = "star_eight"


def curves():
    """The ability curves, bootstrapped from the first-pass ranking."""
    rows, _ = pool_fit.observations()
    order, schools = tiling.ranked()
    filled = tiling.admitted(pool_fit.YEAR)
    groups = tiling.grouped()
    scales = tiling.path_scales(
        tiling.placed_rows(rows, order, schools, groups), filled)
    placed = tiling.seats_in_order(rows, order, schools, groups, scales)
    points, _ = tiling.tile(placed, tiling.assessment_size(pool_fit.YEAR))
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
    if row["path"] in (STAR, STAR_EIGHT):
        level = star_level(row, splines)
        return [] if level is None else [(row["path"], level)]
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


def table(scored, columns, exams, english=None):
    """One ranked row per key, at the seat-weighted ability of its thresholds."""
    english = english or {}
    moment, weight = collect(scored, columns)
    out = []
    for key, sums in moment.items():
        seen = [sums[exam] / weight[key][exam] for exam in exams if weight[key][exam]]
        row = {"rank": 0}
        for column, value in zip(columns, key):
            row[column] = value
            row[f"{column}_en"] = english.get(value, value)
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


def pool_sizes(rows):
    """Estimated annual seats by school and the cohort that holds them.

    These are the same path-scaled seats and assessment denominator used to build
    the exam-to-ability curves. The ranking table's ordinary `seats` column
    remains the observed sample.
    """
    order, schools = tiling.ranked()
    groups = tiling.grouped()
    filled = tiling.admitted(pool_fit.YEAR)
    placed = list(tiling.placed_rows(rows, order, schools, groups))
    scales = tiling.path_scales(placed, filled)
    seats = collections.defaultdict(float)
    for row, _, _ in placed:
        seats[row["school"]] += (float(row["seats"])
                                  * scales.get(row["path"], 1.0))
    return seats, tiling.assessment_size(pool_fit.YEAR)


def add_pool_ratios(rows, seats, cohort):
    """Candidates above a school's ability per cumulative estimated seat."""
    cumulative = 0.0
    start = 0
    while start < len(rows):
        ability = rows[start]["ability"]
        stop = start
        while stop < len(rows) and rows[stop]["ability"] == ability:
            stop += 1
        cumulative += sum(seats.get(row["school"], 0.0)
                          for row in rows[start:stop])
        for row in rows[start:stop]:
            row["pool_seats"] = round(seats.get(row["school"], 0.0), 1)
            row["ability_pool_ratio"] = (
                round(cohort * (1.0 - ability / 100.0) / cumulative, 2)
                if cohort and cumulative else ""
            )
        start = stop
    return rows


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
    names = {row[field] for row in rows
             for field in ("school", "dept", "application_group") if row.get(field)}
    english = english_names(names)
    scored = read(rows, splines)
    exams = sorted({exam for _, exam, _, _ in scored})
    report(scored, exams, rows)
    seats, cohort = pool_sizes(rows)
    print()
    for name, columns in LEVELS:
        found = table(scored, columns, exams, english)
        if columns == ("school",):
            add_pool_ratios(found, seats, cohort)
        written = tsvio.write_rows(ranking_path(name), found)
        print(f"{written:>5} rows -> {name}")


if __name__ == "__main__":
    main()
