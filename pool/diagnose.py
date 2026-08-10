"""Show what treating a bar as a noisy measurement does to real departments.

The fit reports one loading per measurement, which says little on its own. What
it changes is where a department's bars land and whether they land together, so
this prints that department by department, beside the deterministic reading the
ranking pipeline still uses.

`exact` reads every bar as noiseless, which is what the density models do, and
reads a class rank as if it were a national one, which they decline to do at all.
`noisy` is the same densities under the fitted loadings. The gap between the two
rows is the whole of what a loading buys.
"""

import argparse
import os
import sys

# A file invocation puts pool/, rather than the repository root, on sys.path.
if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import diagnose as production
from parse import tcte
from pool import bars, complement, factor, fit as pool_fit

BUCKETS = ("zhikao",) + complement.VOCATIONAL + ("gsat", factor.RANK)
NAMES = {"zhikao": "指考", "gsat": "學測", factor.RANK: "在校排名"}
NAMES.update({pool: tcte.pool_label(pool) for pool in complement.VOCATIONAL})
COLUMN = 11


def deterministic(pool):
    """The same fitted densities read as if every bar were exact."""
    return factor.FactorPool(pool.pool, dict.fromkeys(factor.LOADED, factor.CEILING))


def levels(pool, found):
    """Where each department's bars land, as {department: {bucket: level}}."""
    flat = [(group, name, bar) for group, merged in found.items()
            for name, bar in merged.items()]
    side = factor.Side([bar for _, _, bar in flat], pool.exams)
    got = side.abilities(pool)
    out = {}
    for (group, name, _), level in zip(flat, got):
        out.setdefault(group, {})[name] = 100.0 * level
    return out


def spread(row):
    """How far apart a department's paths put it, in percentile points."""
    seen = [value for value in row.values() if value is not None]
    return max(seen) - min(seen) if len(seen) > 1 else None


def cell(value, width=COLUMN):
    return f"{value:>{width}.1f}" if value is not None else f"{'-':>{width}}"


def table(title, sharp, noisy, found, school):
    """One school's departments, read both ways."""
    depts = sorted((group for group in found if group[1] == school),
                   key=lambda group: -sum(bar.seats for bar in found[group].values()))
    if not depts:
        return
    print(f"\n{school}  ({title})")
    head = production.pad("department", 24) + f"{'reading':>10}"
    head += "".join(f"{NAMES[b]:>{COLUMN - 2}}" for b in BUCKETS) + f"{'spread':>9}"
    print("  " + head)
    print("  " + "-" * production.width(head))
    for group in depts[:production.DEPTS_PER_SCHOOL]:
        for label, source in (("exact", sharp), ("noisy", noisy)):
            row = {b: source[group].get(b) for b in BUCKETS}
            line = production.pad(group[2] if label == "exact" else "", 24)
            line += f"{label:>10}" + "".join(cell(row[b]) for b in BUCKETS)
            gap = spread(row)
            line += cell(gap, 9) if gap is not None else f"{'':>9}"
            print("  " + line)


def summarise(sharp, noisy):
    """How far the loadings moved things, over every department at once."""
    moved, before, after = [], [], []
    for group, exact in sharp.items():
        for name, level in exact.items():
            moved.append(abs(level - noisy[group][name]))
        for measured, into in ((exact, before), (noisy[group], after)):
            gap = spread(measured)
            if gap is not None:
                into.append(gap)
    print(f"\nover {len(sharp)} departments, the loadings move a level by "
          f"{sum(moved) / len(moved):.2f} points on average, at most "
          f"{max(moved):.2f}")
    print(f"  mean disagreement between a department's paths: "
          f"{sum(before) / len(before):.2f} exact, {sum(after) / len(after):.2f} noisy")


def gate_lift(pool, found, limit=8):
    """What the 學測 gates add to a rank bar, which is what identifies a loading."""
    rows = []
    for group, merged in found.items():
        bar = merged.get(factor.RANK)
        if bar is None or not bar.gates:
            continue
        plain = bars.Bar(bar.exam, bar.seats, score=bar.score)
        with_gates = factor.Side([bar], pool.exams).abilities(pool)[0]
        without = factor.Side([plain], pool.exams).abilities(pool)[0]
        rows.append((100 * (with_gates - without), group, bar, 100 * with_gates))
    rows.sort(reverse=True)
    print(f"\nwhat the 檢定 gates add to a 繁星 rank bar, {len(rows)} departments")
    head = production.pad("department", 30) + f"{'rank bar':>10}{'gates':>22}"
    head += f"{'level':>8}{'gate lift':>11}"
    print("  " + head)
    print("  " + "-" * production.width(head))
    for lift, group, bar, level in rows[:limit]:
        gates = " ".join(f"{100 * top:.0f}%" for top in bar.gates)
        name = production.pad(f"{group[1]} {group[2]}", 30)
        rank = float(factor.rank_percentile(bar.score))
        print("  " + name + f"{rank:>9.1f}%" + f"{gates:>22}"
              + f"{level:>8.1f}{lift:>11.1f}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=60,
                        help="SLSQP steps; about 0.9s each at full size")
    args = parser.parse_args()

    got = factor.load()
    observations = bars.flatten(got.groups)
    pool, error = factor.fit(observations, got.sizes, pool_fit.BENDS, steps=args.steps)
    factor.report(pool, observations, error)

    found = bars.collect(got.rows, pool_fit.exam_of, pool_fit.top_of, got.cohort)
    noisy = levels(pool, found)
    sharp = levels(deterministic(pool), found)
    summarise(sharp, noisy)
    print("\nwhere each path puts a department, exact bars against noisy ones")
    for school, kind in production.SCHOOLS:
        table(kind, sharp, noisy, found, school)
    gate_lift(pool, found)


if __name__ == "__main__":
    main()
