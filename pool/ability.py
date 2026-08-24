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
from scipy.stats import norm

from lib import tsvio
from lib.english import english_names
from lib.paths import ranking_path
from pool import fit as pool_fit
from pool import high_school
from pool import tiling

LEVELS = (
    ("ability-universities.tsv", ("school",)),
    ("ability-departments.tsv", ("school", "dept")),
    ("ability-groups.tsv", ("school", "dept", "application_group")),
)
STAR = "star"
STAR_EIGHT = "star_eight"
GRID = 600
REACH = 4.5
# How tightly one 學測 subject tracks ability. The CAP subjects fit 0.897
# against their own joint counts, and 學測 is the same kind of exam.
SUBJECT_LOAD = 0.9


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


def star_bars(row):
    """What 繁星 quotes: a share of one's own school, and a bar in each subject.

    The rank is a share because it counts students inside a school. The 學測
    gates are national, one per subject, and every one of them has to be
    cleared, so a department asking 頂標 of four subjects wants far more than
    the strictest single bar admits.
    """
    rank = None
    if row.get("class_pct") is not None:
        rank = 1.0 - float(row["class_pct"]) / 100.0
    tops = [top for top in (row.get("xuece_tops") or []) if 0.0 < top < 1.0]
    return rank, tops


def one_gate(tops):
    """The strictest single subject bar, as a place on the ability scale."""
    return float(norm.isf(min(tops))) if tops else None


def gate_pass(tops, level, load=SUBJECT_LOAD):
    """Chance of clearing every subject bar at each ability.

    A subject score is this ability plus its own noise, so the subjects agree
    often but not always. Clearing four bars is therefore far rarer than
    clearing the hardest one and far commoner than four independent draws, and
    only the whole product says where a wall of 頂標 actually lands.
    """
    if not tops:
        return np.ones_like(level)
    spread = (1.0 - load ** 2) ** 0.5
    out = np.ones_like(level)
    for top in tops:
        out = out * norm.sf((norm.isf(top) - load * level) / spread)
    return out


def eligible_floors(rank, gate, means, spread):
    """Where each school's students stop qualifying, in that school's own terms.

    The size of the qualifying group says nothing on its own, because the top
    tenth of every school is a tenth of the country however the schools are
    arranged. What the bars settle is who those students are, and they bind
    school by school: the rank cuts every school at the same depth, while the
    gate cuts deeper the weaker the school, until it passes above one entirely.
    """
    means = np.asarray(means, dtype=float)
    floor = np.full(means.shape, -np.inf)
    if rank is not None:
        floor = np.full(means.shape, float(norm.isf(rank)))
    if gate is not None:
        floor = np.maximum(floor, (gate - means) / spread)
    return means, floor


def qualifying_ability(rank, gate, means, spread):
    """Mean ability of everyone both bars leave eligible."""
    means, floor = eligible_floors(rank, gate, means, spread)
    left = norm.sf(floor)
    if left.sum() <= 0:
        return None
    return float((means * left + spread * norm.pdf(floor)).sum() / left.sum())


def marginal_ability(rank, gate, means, spread, wanted, cohort):
    """Ability of the weakest of the `wanted` students a department could take.

    The alternative to sweeping: read each department alone, at the bottom of
    its own eligible group, the way every other path is read at its margin. It
    suits a department whose bars barely reach the people it needs, and it
    understates one whose pool dwarfs its intake, because the weakest few of a
    large group sit wherever the bars fall.
    """
    means, floor = eligible_floors(rank, gate, means, spread)
    share = wanted / cohort if cohort else 0.0
    if share <= 0 or norm.sf(floor).mean() <= share:
        return qualifying_ability(rank, gate, means, spread)

    def below(level):
        """Share of the cohort that qualifies and sits under `level`."""
        reached = (level - means) / spread
        return float(np.maximum(0.0, norm.cdf(reached) - norm.cdf(floor)).mean())

    low = float(np.min(means + spread * floor))
    high = float(np.max(means) + 8.0 * spread)
    for _ in range(80):
        middle = 0.5 * (low + high)
        if below(middle) < share:
            low = middle
        else:
            high = middle
    return 0.5 * (low + high)


DEFAULT_COHORT = 300


def paired(atoms):
    """Accept bare school means as well as (mean, cohort size) pairs."""
    return [item if isinstance(item, tuple) else (item, DEFAULT_COHORT)
            for item in atoms]


def on_pool_scale(atoms, sitting):
    """Move school means from the 會考 cohort onto the pool that sits 學測.

    A cutoff counts everyone who sat 會考, while a 學測 gate counts only those
    who reached the exam three years later. Comparing the two without saying so
    puts every school lower than it belongs, which is why the reading needed a
    curve afterwards to look right.
    """
    if not sitting or sitting >= 1.0:
        return atoms
    out = []
    for mean, size in atoms:
        share = float(np.clip(norm.sf(mean) / sitting, 1e-9, 1.0))
        out.append((float(norm.isf(share)), size))
    return out


def pool_grid(atoms, spread):
    """Ability grid and the weight each school starts with on it."""
    level = np.linspace(-REACH, REACH, GRID)
    step = level[1] - level[0]
    means = np.array([mean for mean, _ in atoms], dtype=float)
    weight = norm.pdf((level[None, :] - means[:, None]) / spread) / spread
    return level, weight * step / len(atoms)


def rank_cuts(rank, atoms, means, spread, level):
    """Grid index where each school's class-rank bar falls.

    The published rank is a whole percent rounded up, so a school of 300 can
    put forward three students at 1% and a school of 60 can put forward none.
    Taking the count first and the share second keeps that.
    """
    if rank is None:
        return np.zeros(len(atoms), dtype=int)
    counted = np.array([int(rank * size) for _, size in atoms], dtype=float)
    sizes = np.array([size for _, size in atoms], dtype=float)
    shares = np.divide(counted, sizes, out=np.zeros_like(sizes), where=sizes > 0)
    cuts = np.where(shares > 0, means + spread * norm.isf(np.clip(shares, 1e-12, 1)),
                    np.inf)
    return np.searchsorted(level, cuts)


def draw(weight, level, cuts, passing, wanted):
    """Mean ability of everyone a department can reach, and the pool it leaves.

    It does not take those people cleanly, because the departments behind it
    draw on the same students, so the places it fills are thinned rather than
    removed.
    """
    reach = np.arange(len(level))[None, :] >= cuts[:, None]
    live = weight * reach * passing[None, :]
    mass = live.sum()
    if mass <= 0:
        return None, weight
    found = float((live * level[None, :]).sum() / mass)
    left = max(0.0, 1.0 - wanted / mass)
    return found, weight - live * (1.0 - left)


def star_sweep(rows, atoms, cohort, sitting=None, spread=high_school.SPREAD):
    """Read every 繁星 department, strictest first, thinning the pool as it goes.

    Ordering by what each department's own bars reach keeps the published
    ranking out of the score, and sweeping in that order lets a department
    already served leave a shallower pool to the ones behind it.
    """
    atoms = on_pool_scale(paired(atoms), sitting)
    level, start = pool_grid(atoms, spread)
    means = np.array([mean for mean, _ in atoms], dtype=float)
    ready = []
    for row in rows:
        if row["path"] not in (STAR, STAR_EIGHT):
            continue
        rank, tops = star_bars(row)
        if rank is None and not tops:
            continue
        cuts = rank_cuts(rank, atoms, means, spread, level)
        passing = gate_pass(tops, level)
        alone, _ = draw(start, level, cuts, passing, 0.0)
        if alone is None:
            continue
        wanted = float(row.get("screened") or row.get("seats") or 0) / cohort
        ready.append((alone, row, cuts, passing, wanted))
    ready.sort(key=lambda item: -item[0])
    weight, out = start, {}
    for _, row, cuts, passing, wanted in ready:
        found, weight = draw(weight, level, cuts, passing, wanted)
        if found is not None:
            out[id(row)] = found
    return out


def star_level(row, splines, swept):
    """繁星's reading, already an ability and so needing no curve of its own.

    Every other path reads a share of one exam's takers and needs a curve to
    price it. This one has been worked out on the ability scale from the start,
    so pricing it again would put it through a conversion it has already had.
    """
    level = swept.get(id(row))
    return None if level is None else float(np.clip(norm.cdf(level), 0.0, 1.0))


def levels(row, splines, swept):
    """Every ability a row's thresholds imply, tagged by what produced each."""
    exam = pool_fit.exam_of(row)
    if exam is None:
        return []
    if row["path"] in (STAR, STAR_EIGHT):
        level = star_level(row, splines, swept)
        return [] if level is None else [(row["path"], level)]
    top = pool_fit.top_of(row) if exam in splines else None
    return [] if top is None else [(exam, held(splines[exam], 1.0 - top))]


def read(rows, splines, means=None, cohort=None, sitting=None):
    """Turn every readable threshold into an ability, through its own curve."""
    means = high_school.atoms() if means is None else means
    if cohort is None:
        cohort = tiling.assessment_size(pool_fit.YEAR)
    if sitting is None:
        sitting = cohort / high_school.cap_takers()
    swept = star_sweep(rows, means, cohort, sitting)
    return [(row, exam, level, float(row["seats"]))
            for row in rows for exam, level in levels(row, splines, swept)]


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
