"""Score every department by the ability its own thresholds imply.

A threshold is a percentile inside one exam, and annual seat tiling says what it
is worth in cohort ability. A department admitting through three exams therefore
holds three readings of its margins, and its score is their seat-weighted average.
No separately generated rank or cross-route latent bridge enters the calculation.
"""

import collections

if __package__ in (None, ""):
    import _bootstrap  # noqa: F401

import numpy as np
from scipy.stats import norm

from lib import deptname, schoolname, tsvio
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
YEARS = tuple(str(year) for year in range(107, 116))
CURVE_ITERATIONS = 12
CURVE_TOLERANCE = 1e-5


def admission_rows():
    """All raw threshold rows, without the legacy ranking bridge."""
    rows, _, _ = pool_fit.source_rows()
    pool_fit.attach_apply_tops(rows)
    return rows


def assessment_size(year):
    """Annual assessment pool, scaling the measured 110 union by takers."""
    exact = tiling.assessment_size(year)
    if exact:
        return exact
    base = tiling.assessment_size(pool_fit.YEAR)
    current = pool_fit.taker_counts(year)
    reference = pool_fit.taker_counts(pool_fit.YEAR)
    vocational = sum(current.get(f"tongce_{group}", 0.0) for group in "abc")
    base_vocational = sum(reference[f"tongce_{group}"] for group in "abc")
    if vocational:
        share = base / (reference["gsat"] + base_vocational)
        return share * (current["gsat"] + vocational)
    return base * current["gsat"] / reference["gsat"]


def initial_levels(rows):
    """Start only from each bar's direction inside its own exam."""
    return {id(row): 1.0 - top for row in rows
            if (top := pool_fit.top_of(row)) is not None}


def fallback_levels(rows, levels):
    """Department and school means place rows without a direct margin."""
    departments = collections.defaultdict(list)
    schools = collections.defaultdict(list)
    for row in rows:
        if id(row) not in levels:
            continue
        value, seats = levels[id(row)], float(row["seats"])
        departments[(row["school"], row["dept"])].append((value, seats))
        schools[row["school"]].append((value, seats))
    department = {key: weighted(values) for key, values in departments.items()}
    school = {key: weighted(values) for key, values in schools.items()}
    return department, school


def weighted(values):
    total = sum(weight for _, weight in values)
    return sum(value * weight for value, weight in values) / total if total else None


def placed_rows(rows, levels, year):
    """Place one year's seats using only the ability model's current readings."""
    departments, schools = fallback_levels(rows, levels)
    raw = []
    for row in rows:
        exam = pool_fit.exam_of(row)
        key = row["school"], row["dept"]
        score = levels.get(id(row), departments.get(key, schools.get(row["school"])))
        if exam is not None and score is not None:
            raw.append((row, score, exam))
    scales = tiling.path_scales(raw, tiling.admitted(year))
    placed = [(score, exam, pool_fit.top_of(row),
               float(row["seats"]) * scales.get(row["path"], 1.0))
              for row, score, exam in raw]
    return sorted(placed, key=lambda item: -item[0])


def direct_levels(rows, splines):
    """Read final-cutoff and screen bars through their own exam curve."""
    out = {}
    for row in rows:
        exam, top = pool_fit.exam_of(row), pool_fit.top_of(row)
        if exam in splines and top is not None:
            out[id(row)] = held(splines[exam], 1.0 - top)
    return out


def fit_year(rows, year, iterations=CURVE_ITERATIONS):
    """Alternate seat ordering and exam curves to a self-contained fixed point."""
    levels = initial_levels(rows)
    if not levels:
        return {}, levels, 0
    for iteration in range(1, iterations + 1):
        placed = placed_rows(rows, levels, year)
        points, _ = tiling.tile(placed, assessment_size(year))
        splines = tiling.splines(points)
        updated = direct_levels(rows, splines)
        common = set(levels) & set(updated)
        difference = max((abs(updated[key] - levels[key]) for key in common),
                         default=0.0)
        levels = updated
        if difference < CURVE_TOLERANCE:
            break
    placed = placed_rows(rows, levels, year)
    points, _ = tiling.tile(placed, assessment_size(year))
    return tiling.splines(points), levels, iteration


def curves(year=pool_fit.YEAR):
    """One year's ability curves, independent of legacy rank files."""
    rows = [row for row in admission_rows() if row["year"] == str(year)]
    splines, _, _ = fit_year(rows, str(year))
    return rows, splines


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


def longitudinal(years=YEARS):
    """Score every available year through a separately fitted ability curve."""
    source = admission_rows()
    scored, fitted = [], {}
    for year in years:
        rows = [row for row in source if row["year"] == year]
        splines, _, iterations = fit_year(rows, year)
        if not splines:
            print(f"{year}: no readable final-cutoff curve; annual panel will impute")
            continue
        cohort = assessment_size(year)
        found = read(rows, splines, cohort=cohort,
                     sitting=cohort / high_school.cap_takers())
        scored.extend(found)
        fitted[year] = splines
        print(f"{year}: {len(found):,} threshold readings, {len(splines)} exams, "
              f"{iterations} iterations")
    return source, scored, fitted


def history_inputs(scored):
    """Rows carrying cohort ability for annual seat completion."""
    out = []
    for row, _, level, seats in scored:
        found = dict(row)
        found["score"], found["seats"] = 100.0 * level, seats
        out.append(found)
    return out


def current_key(row, columns):
    """Output key, merging predecessor institutions only at school level."""
    values = tuple(row[column] for column in columns)
    if columns == ("school",):
        return (schoolname.current(values[0]),)
    return values


def collect(scored, columns):
    """Seat-weighted ability for each key, kept per exam and over all of them."""
    moment = collections.defaultdict(lambda: collections.defaultdict(float))
    weight = collections.defaultdict(lambda: collections.defaultdict(float))
    years = collections.defaultdict(set)
    for row, exam, level, seats in scored:
        key = current_key(row, columns)
        years[key].add(row["year"])
        for name in ("all", exam):
            moment[key][name] += level * seats
            weight[key][name] += seats
    return moment, weight, years


def school_english(name, english):
    """Prefer official English names for institutions involved in mergers."""
    return schoolname.OFFICIAL_ENGLISH.get(name, english.get(name, ""))


def table(scored, columns, exams, english=None):
    """One ranked row per key, at the seat-weighted ability of its thresholds."""
    english = english or {}
    moment, weight, years = collect(scored, columns)
    out = []
    for key, sums in moment.items():
        seen = [sums[exam] / weight[key][exam] for exam in exams if weight[key][exam]]
        row = {"rank": 0}
        for column, value in zip(columns, key):
            row[column] = value
            row[f"{column}_en"] = (school_english(value, english)
                                    if column == "school"
                                    else english.get(value, ""))
        if columns == ("school",):
            former = schoolname.FORMER.get(row["school"], ())
            row["former_schools"] = " | ".join(former)
            row["former_schools_en"] = " | ".join(
                school_english(name, english) for name in former
            )
        row["ability"] = round(100 * sums["all"] / weight[key]["all"], 2)
        row["seats"] = round(weight[key]["all"], 1)
        row["years"] = len(years[key])
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


def normalized_scored(scored):
    """Use the annual panel's institution and department identities."""
    out = []
    for row, exam, level, seats in scored:
        found = dict(row)
        found["school"] = schoolname.without_campus(schoolname.current(row["school"]))
        found["dept"] = deptname.normalize(row["dept"])
        out.append((found, exam, level, seats))
    return out


def annual_table(history, scored, columns, exams, english=None):
    """Aggregate completed annual ability while retaining direct exam readings."""
    from rank import annual

    english = english or {}
    direct = table(normalized_scored(scored), columns, exams, english)
    direct = {tuple(row[column] for column in columns): row for row in direct}
    out = []
    for aggregate in annual.aggregate(history, columns):
        key = aggregate["key"]
        key = key if isinstance(key, tuple) else (key,)
        readings = direct.get(key, {})
        row = {"rank": 0}
        for column, value in zip(columns, key):
            row[column] = value
            row[f"{column}_en"] = (school_english(value, english)
                                    if column == "school"
                                    else english.get(value, ""))
        if columns == ("school",):
            former = schoolname.FORMER.get(row["school"], ())
            row["former_schools"] = " | ".join(former)
            row["former_schools_en"] = " | ".join(
                school_english(name, english) for name in former)
        row["ability"] = round(aggregate["score"], 2)
        row["seats"] = round(aggregate["seats_avg"], 1)
        row["years"], row["last_year"] = aggregate["years"], aggregate["last_year"]
        row["spread"] = readings.get("spread", "")
        for exam in exams:
            row[exam] = readings.get(exam, "")
        out.append(row)
    out.sort(key=lambda row: -row["ability"])
    for rank, row in enumerate(out, 1):
        row["rank"] = rank
    return out


def disagreement(scored, exams):
    """Seat-weighted gap between the exams scoring one department, by decile."""
    moment, weight, _ = collect(scored, ("school", "dept"))
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
    """Average annual completed seats by school and assessment-pool size."""
    from rank import annual

    aggregates = annual.aggregate(rows, ("school",))
    seats = {row["key"]: row["seats_avg"] for row in aggregates}
    years = sorted({str(row["year"]) for row in rows})
    cohorts = [assessment_size(year) for year in years]
    return seats, sum(cohorts) / len(cohorts) if cohorts else 0.0


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
    from rank import annual

    rows, scored, _ = longitudinal()
    history = annual.build(history_inputs(scored))
    annual.write(history, ranking_path("ability-history.tsv"))
    names = {row[field] for row, _, _, _ in scored
             for field in ("school", "dept", "application_group") if row.get(field)}
    names |= {row[field] for row in history for field in ("school", "dept")}
    english = english_names(names)
    exams = sorted({exam for _, exam, _, _ in scored})
    report(scored, exams, rows)
    seats, cohort = pool_sizes(history)
    print()
    for name, columns in LEVELS:
        found = (table(scored, columns, exams, english)
                 if columns == ("school", "dept", "application_group")
                 else annual_table(history, scored, columns, exams, english))
        if columns == ("school",):
            add_pool_ratios(found, seats, cohort)
        written = tsvio.write_rows(ranking_path(name), found)
        print(f"{written:>5} rows -> {name}")


if __name__ == "__main__":
    main()
