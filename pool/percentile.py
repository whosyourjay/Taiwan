"""Rank one 學測 total against the cohort, and against the admitted pool.

A candidate's score is a bar like any department's: clear it and you hold the
ability behind it. So the score goes through the same two steps a department's
own cutoff goes through — the published distribution says what share of takers
it beats, and that exam's curve says what that share is worth in the pool.
"""

import functools
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ceec_score
from lib.paths import data_path
from pool import ability

EXAM = "gsat"


@functools.lru_cache(maxsize=1)
def sources():
    """學測 distributions and the exam curves, built once per process."""
    cohort = ceec_score.CohortPercentiles.load(data_path("ceec-scores.tsv"))
    return cohort, ability.curves()[1]


def rank(year, label, score, loaded=None):
    """Where a 學測 total sits, as ``(share of takers it beats, pool ability)``.

    `label` names the subjects the total covers the way a 篩選 bar does, so
    國英數社自 is the five-subject total published through 107 and 國英數自 is
    one of the combination totals published from 108. Returns ``(None, None)``
    when that year published no distribution for that subject set.
    """
    cohort, splines = loaded or sources()
    top = cohort.top_fraction(year, label, score)
    if top is None:
        return None, None
    below = 1.0 - top
    return below, ability.held(splines[EXAM], below)


def main(argv):
    if len(argv) != 3:
        print("usage: python3 -m pool.percentile YEAR SUBJECTS SCORE\n"
              "   eg: python3 -m pool.percentile 103 國英數社自 65", file=sys.stderr)
        return 1
    year, label, score = argv[0], argv[1], float(argv[2])
    below, level = rank(year, label, score)
    if below is None:
        print(f"{year} published no 學測 distribution for {label}", file=sys.stderr)
        return 1
    print(f"{label} {score:g} in {year}")
    print(f"  beats {100 * below:.2f}% of 學測 takers")
    print(f"  pool ability {100 * level:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
