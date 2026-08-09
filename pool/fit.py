"""Fit the cohort-ability model and report what it says about each exam.

分發入學 quotes a 指考 bar, 繁星 and 個人申請 quote a 學測 bar. Where one
department admits through both, the two bars describe the same margin, so the
gap between the abilities they imply is the error to minimise.
"""

import collections
import contextlib
import math
import sys

import ceec_score
import rank_uac
from lib.paths import path
from pool import model

# 110 is the year every school was collected for, and the last year 分發入學 ran
# purely on 指考 — from 111 its formulas mix in 學測 subjects.
YEAR = "110"
BINS = 3


EXAMS = {"uac": "zhikao", "tech": "tongce", "star": "gsat", "apply": "gsat"}


def exam_of(row):
    """Which exam pool a row's bar is a percentile inside."""
    return EXAMS.get(row["path"]) if row["year"] == YEAR else None


def top_of(row):
    """Share of that exam's takers who cleared the bar."""
    if row["path"] in ("uac", "tech"):
        percentile = row.get("ceec_percentile")
        return None if percentile is None else 1.0 - percentile
    if row["path"] == "apply":
        return row.get("cohort_top")
    # 繁星 ranks inside a school, so its bar is not a cohort percentile. The
    # 檢定 gates are, but they are a floor rather than the margin.
    return None


def attach_apply_tops(rows):
    """Read each 個人申請 bar against the 學測 級分 distribution."""
    cohort = ceec_score.CohortPercentiles.load(path("ceec-scores.tsv"))
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


GLYPHS = {"gsat": "o", "zhikao": "x", "tongce": "+"}
NAMES = {"gsat": "學測", "zhikao": "指考/分科測驗", "tongce": "統測"}


def plot_densities(pool_fit, height=16, width=66):
    """Overlaid step plot of every exam's taker density over cohort ability.

    Each curve is independent and they may overlap by any amount. Drawing them
    on one axis shows where a percentile in one exam stops meaning what it means
    in another; it says nothing about which students sat both.
    """
    exams = sorted(pool_fit.shares)
    density = {e: pool_fit.percentile_density(e) for e in exams}
    ceiling = math.ceil(max(max(d) for d in density.values()) / 100) * 100

    print("\ntakers per cohort-percentile point"
          "   (area under a curve = observed takers)")
    for row in range(height, 0, -1):
        level = ceiling * row / height
        line = ""
        for col in range(width):
            k = min(pool_fit.bins - 1, col * pool_fit.bins // width)
            hit = [e for e in exams if density[e][k] >= level]
            line += "#" if len(hit) > 1 else (GLYPHS.get(hit[0], "*") if hit else " ")
        print(f"  {level:5.0f} |{line}")
    print("        +" + "-" * width)
    ticks = "        "
    for mark in (0, 25, 50, 75, 100):
        cell = 1 + mark * (width - 1) // 100
        ticks = ticks.ljust(8 + cell - len(str(mark)) // 2) + str(mark)
    print(ticks)
    print(" " * 8 + "cohort ability percentile (100 = top)")
    print("  " + "   ".join(f"{GLYPHS.get(e, '*')} {NAMES.get(e, e)}" for e in exams)
          + "   # two or more")
    missing = [e for e in NAMES if e not in exams]
    if missing:
        print("  not fitted: " + ", ".join(NAMES[e] for e in missing)
              + " — no published score distribution collected yet")


def report(pool_fit, observations, error):
    print(f"\nfit on {len(observations)} matched threshold pairs, {YEAR}")
    pairs = collections.Counter(
        tuple(sorted((left, right))) for left, _, right, _, _ in observations
    )
    print("  " + ", ".join(
        f"{left}-{right}: {count}" for (left, right), count in sorted(pairs.items())
    ))
    print(f"  taking percentiles as comparable: {naive_error(observations):5.2f} points")
    print(f"  after placing all on the cohort:   {error:5.2f} points")

    print("\nfitted takers in each cohort-ability bin")
    header = "  " + f"{'exam':<9}{'observed':>11}" + "".join(
        f"{f'{100*k//BINS}-{100*(k+1)//BINS}%':>12}" for k in range(BINS)
    )
    print(header)
    print("  " + "-" * (len(header) - 2))
    for exam in sorted(pool_fit.shares):
        counts = pool_fit.bin_counts(exam)
        print("  " + f"{exam:<9}{pool_fit.sizes[exam]:>11,.0f}"
              + "".join(f"{n:>12,.0f}" for n in counts))

    plot_densities(pool_fit)

    print("\nwhere a bar lands on the cohort, by exam")
    names = sorted(pool_fit.shares)
    print("  " + f"{'top of takers':<20}" + "".join(f"{e:>12}" for e in names))
    for top in (0.01, 0.05, 0.10, 0.25, 0.50):
        cells = "".join(f"{100 * pool_fit.ability(e, top):>11.1f}%" for e in names)
        print("  " + f"top {100 * top:>4.0f}% of takers".ljust(20) + cells)


def observations():
    """Run the pipeline and pair up departments admitting through two exams."""
    with contextlib.redirect_stdout(sys.stderr):
        rows = rank_uac.build_rows()
    resolved = attach_apply_tops(rows)
    matched = model.matched(rows, exam_of, top_of)
    print(f"{resolved} 個人申請 bars read against the 學測 cohort", file=sys.stderr)
    return rows, matched


def main():
    _, matched = observations()
    if not matched:
        print("no matched departments; nothing to fit", file=sys.stderr)
        return
    exams = sorted({e for o in matched for e in (o[0], o[2])})
    sizes = taker_counts()
    fitted, error = model.fit(matched, exams, sizes, bins=BINS)
    report(fitted, matched, error)


def taker_counts():
    """How many sat each exam in YEAR, from the published distributions."""
    import csv

    totals = collections.defaultdict(lambda: collections.defaultdict(float))
    for name in ("ceec-scores.tsv", "tongce-scores.tsv"):
        with open(path(name), encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                if row["year"] != YEAR or "、" in row["subject"]:
                    continue
                totals[row["exam"]][row["subject"]] += float(row["seats"])
    # The most-sat subject is the closest thing to a headcount: everyone sits
    # 國文, but the science and language papers split the cohort.
    return {exam: max(subjects.values()) for exam, subjects in totals.items()}


if __name__ == "__main__":
    main()
