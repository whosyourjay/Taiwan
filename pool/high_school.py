"""Place every high school we can read on the national ability scale.

A district admits on its own 超額比序 total, and each of those totals is a
function of 會考 marks, so the published national mark counts turn a school's
cutoff into a share of the country. 基北 scores the plus marks and needs the
fitted 36-point distribution; the coarse districts score only 精熟, 基礎 and
待加強, which the category counts settle outright.

What comes out is a floor per school rather than a mean, and the coarse scales
run out of room at five 精熟, so their strongest schools all land together at
the ceiling.
"""

import collections
import re
import statistics
import sys

if __package__ in (None, ""):
    import _bootstrap  # noqa: F401

from scipy.stats import norm

from lib import tsvio
from lib.paths import data_path
from pool.entry_score import grade_scores

CUTOFFS = "high-school-entry-cutoffs.tsv"
ENTRY_SCORES = "cap-entry-scores.tsv"
CATEGORIES = "cap-grade-distributions.tsv"
SIZES = "high-school-sizes.tsv"
OUTPUT = "high-school-ability.tsv"
# 基北 is the only district whose total separates A++ from a bare A.
FINE = "基北區"
# Districts scoring only 精熟, 基礎 and 待加強. 桃連 adds 寫作測驗 worth up to
# three points on top of the same grid, and every cutoff it publishes carries
# the full three.
COARSE = {"竹苗區": 0.0, "中投區": 0.0, "高雄區": 0.0, "桃連區": 3.0}
# The year covering four districts rather than one.
ATOM_YEAR = "114"
# Within-school spread on the ability scale. PISA 2022 puts 38% of Chinese
# Taipei's variance between schools and these cutoffs put 47%, so 0.75 sits
# between the two readings.
SPREAD = 0.75


def running(shares):
    """Turn a share at each score into the share at or above it."""
    out, above = {}, 0.0
    for score in sorted(shares, reverse=True):
        above += shares[score]
        out[float(score)] = above
    return out


def scales():
    """One score-to-national-share table per district scale."""
    fine = {float(row["score"]): float(row["pct_at_or_above"]) / 100
            for row in tsvio.read_rows(data_path(ENTRY_SCORES))}
    coarse = running(grade_scores(tsvio.read_rows(data_path(CATEGORIES))))
    shifted = {name: {score + offset: share for score, share in coarse.items()}
               for name, offset in COARSE.items()}
    return {FINE: fine, **shifted}


def cutoff_levels():
    """Every cutoff on a scale we can read, placed on the ability scale."""
    tables = scales()
    ceiling = {name: max(table) for name, table in tables.items()}
    out, skipped = [], collections.Counter()
    for row in tsvio.read_rows(data_path(CUTOFFS)):
        table = tables.get(row["district"])
        score = float(row["cap_score"])
        share = table.get(score) if table else None
        if share is None:
            skipped[row["district"]] += 1
            continue
        out.append({
            "year": row["year"],
            "district": row["district"],
            "school": row["school"],
            "cap_score": row["cap_score"],
            "pct_above": round(100 * share, 4),
            "cutoff_z": round(float(norm.isf(share)), 4),
            "at_ceiling": int(score >= ceiling[row["district"]]),
        })
    return sorted(out, key=lambda row: -row["cutoff_z"]), skipped


def cohorts(year=ATOM_YEAR):
    """Graduating cohort per school name, for the year the atoms come from."""
    out = {}
    for row in tsvio.read_rows(data_path(SIZES)):
        if row["year"] == year and int(row["graduates"]):
            out[trimmed(row["school"])] = int(row["graduates"])
    return out


def trimmed(name):
    """A school name without the prefix that says who runs it."""
    return re.sub(r"^(國立|市立|私立|縣立)", "", name).strip()


def atoms(year=ATOM_YEAR):
    """Each school's ability mean and cohort size, as 繁星 recommends from them.

    A cutoff sits below the school's own CAP mean, while its ability mean sits
    below where its CAP standing would put it, because three years of schooling
    pull a school back toward the middle. Nothing here separates the two, so the
    cutoff stands as the estimate and the offsets are left to cancel.
    """
    rows, _ = cutoff_levels()
    sizes = cohorts(year)
    placed = [row for row in rows if row["year"] == year]
    typical = statistics.median(sizes.values()) if sizes else 0
    return [(row["cutoff_z"], sizes.get(trimmed(row["school"]), typical))
            for row in placed]


def report(rows, skipped, out=sys.stderr):
    """Coverage and resolution, by district and year."""
    groups = collections.defaultdict(list)
    for row in rows:
        groups[(row["year"], row["district"])].append(row)
    print(f"{'year':<6}{'district':<10}{'schools':>8}{'distinct':>10}"
          f"{'top z':>8}{'bottom z':>10}{'at ceiling':>12}", file=out)
    for (year, district), found in sorted(groups.items()):
        levels = {row["cap_score"] for row in found}
        tops = [row["cutoff_z"] for row in found]
        stuck = sum(row["at_ceiling"] for row in found)
        print(f"{year:<6}{district:<10}{len(found):>8}{len(levels):>10}"
              f"{max(tops):>8.2f}{min(tops):>10.2f}{stuck:>12}", file=out)
    for district, count in sorted(skipped.items()):
        print(f"skipped {count} {district} cutoffs, scale not read", file=out)


def main():
    rows, skipped = cutoff_levels()
    report(rows, skipped)
    written = tsvio.write_rows(data_path(OUTPUT), rows)
    print(f"\nwrote {written} rows to {data_path(OUTPUT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    main()
