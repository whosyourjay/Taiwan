"""Fit the cohort-ability model and report what it says about each exam.

分發入學 quotes a 指考 bar, 繁星 and 個人申請 quote a 學測 bar. Where one
department admits through both, the two bars describe the same margin, so the
gap between the abilities they imply is the error to minimise.
"""

import collections
import contextlib
import os
import sys

import ceec_score
import pool
import rank_uac

HERE = os.path.dirname(os.path.abspath(__file__))
# 110 is the year every school was collected for, and the last year 分發入學 ran
# purely on 指考 — from 111 its formulas mix in 學測 subjects.
YEAR = "110"
BINS = 3


def exam_of(row):
    """Which exam pool a row's bar is a percentile inside."""
    if row["year"] != YEAR:
        return None
    if row["path"] == "uac":
        return "zhikao"
    if row["path"] in ("star", "apply"):
        return "gsat"
    return None


def top_of(row):
    """Share of that exam's takers who cleared the bar."""
    if row["path"] == "uac":
        percentile = row.get("ceec_percentile")
        return None if percentile is None else 1.0 - percentile
    if row["path"] == "apply":
        return row.get("cohort_top")
    if row["path"] == "star":
        # 繁星 ranks inside a school, so its bar is not a cohort percentile. The
        # 檢定 gates are, but they are a floor rather than the margin.
        return None
    return None


def attach_apply_tops(rows):
    """Read each 個人申請 bar against the 學測 級分 distribution."""
    cohort = ceec_score.CohortPercentiles.load(os.path.join(HERE, "ceec-scores.tsv"))
    got = 0
    for row in rows:
        if row["path"] != "apply":
            continue
        top = cohort.top_fraction(row["year"], row["cut_label"], row["cut_level"])
        if top is not None:
            row["cohort_top"] = top
            got += 1
    return got


def naive_error(observations):
    """Disagreement if a percentile inside one exam is read as another's."""
    total = weight = 0.0
    for _, top_a, _, top_b, w in observations:
        total += w * abs(top_a - top_b)
        weight += w
    return 100.0 * total / weight if weight else 0.0


def report(pool_fit, sizes, observations, error):
    print(f"\nfit on {len(observations)} matched departments, {YEAR}")
    print(f"  taking percentiles as comparable: {naive_error(observations):5.2f} points")
    print(f"  after placing both on the cohort:  {error:5.2f} points")

    print("\nhow each exam's takers sit on the cohort (1.00 = its fair share)")
    header = "  " + f"{'exam':<9}{'takers':>9}" + "".join(
        f"{f'{100*k//BINS}-{100*(k+1)//BINS}%':>10}" for k in range(BINS)
    )
    print(header)
    print("  " + "-" * (len(header) - 2))
    for exam in sorted(pool_fit.shares):
        shares = pool_fit.shares[exam]
        print("  " + f"{exam:<9}{sizes[exam]:>9,.0f}"
              + "".join(f"{BINS * s:>10.2f}" for s in shares))

    print("\nwhere a bar lands on the cohort, by exam")
    names = sorted(pool_fit.shares)
    print("  " + f"{'top of takers':<20}" + "".join(f"{e:>12}" for e in names))
    for top in (0.01, 0.05, 0.10, 0.25, 0.50):
        cells = "".join(f"{100 * pool_fit.ability(e, top):>11.1f}%" for e in names)
        print("  " + f"top {100 * top:>4.0f}% of takers".ljust(20) + cells)


def main():
    with contextlib.redirect_stdout(sys.stderr):
        rows = rank_uac.build_rows()
    resolved = attach_apply_tops(rows)

    observations = pool.matched(rows, exam_of, top_of)
    if not observations:
        print("no matched departments; nothing to fit", file=sys.stderr)
        return
    print(f"{resolved} 個人申請 bars read against the 學測 cohort", file=sys.stderr)

    sizes = taker_counts()
    fitted, error = pool.fit(observations, sorted({e for o in observations
                                                   for e in (o[0], o[2])}),
                             bins=BINS)
    report(fitted, sizes, observations, error)


def taker_counts():
    """How many sat each exam in YEAR, from the published distributions."""
    import csv

    totals = collections.defaultdict(lambda: collections.defaultdict(float))
    path = os.path.join(HERE, "ceec-scores.tsv")
    with open(path, encoding="utf-8") as f:
        for row in csv.DictReader(f, delimiter="\t"):
            if row["year"] != YEAR or "、" in row["subject"]:
                continue
            totals[row["exam"]][row["subject"]] += float(row["seats"])
    return {"gsat": max(totals["gsat"].values()),
            "zhikao": max(totals["zhikao"].values())}


if __name__ == "__main__":
    main()
