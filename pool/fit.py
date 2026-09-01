"""Fit the cohort-ability model and report what it says about each exam.

分發入學 quotes a 指考 bar, 繁星 and 個人申請 quote a 學測 bar. Where one
department admits through both, the two bars describe the same margin, so the
gap between the abilities they imply is the error to minimise.
"""

import collections
import sys

if __package__ in (None, ""):
    import _bootstrap  # noqa: F401

from lib import tsvio
from lib.paths import data_path
from parse import tcte
from pool import complement, model
from rank import ceec_score, uac

# 110 is the year every school was collected for, and the last year 分發入學 ran
# purely on 指考 — from 111 its formulas mix in 學測 subjects.
YEAR = "110"

# Held-out error picks the bend count in pool/compare.py; four and five are a
# coin flip against three. It keeps preferring more overlap than anyone believes,
# and spends all of it at a single ability, so this is a judgement about how many
# students sit both 學測 and 統測 rather than something the thresholds decide.
BENDS = 3
OVERLAP = 0.05


def fit_pool(observations, sizes):
    """Fit the chosen model: densities that stack into a possible population."""
    return complement.fit(observations, sizes, BENDS, overlap=OVERLAP)


EXAMS = {
    "uac": "zhikao",
    "star": "gsat",
    "star_eight": "gsat",
    "apply": "gsat",
    "tech_apply": "gsat",
}


def exam_of(row):
    """Which exam pool a row's bar is a percentile inside.

    A 統測 bar is a percentile inside the 群 that sat its 數學 paper, not
    inside 統測 as a whole, because no student sits two of those papers.
    """
    if row["path"] == "tech":
        return tcte.math_pool(row["group"])
    return EXAMS.get(row["path"])


def top_of(row):
    """Share of that exam's takers who cleared the bar."""
    if row["path"] in ("uac", "tech", "tech_apply"):
        percentile = row.get("ceec_percentile")
        return None if percentile is None else 1.0 - percentile
    if row["path"] == "apply":
        return row.get("cohort_top")
    # 繁星 ranks inside a school, so its bar is not a cohort percentile. The
    # 檢定 gates are, but they are a floor rather than the margin.
    return None


def attach_apply_tops(rows):
    """Read each 個人申請 bar against the 學測 級分 distribution."""
    cohort = ceec_score.CohortPercentiles.load(data_path("ceec-scores.tsv"))
    got = 0
    for row in rows:
        if row["path"] != "apply":
            continue
        top = cohort.top_fraction(row["year"], row["cut_label"], row["cut_level"])
        if top is not None:
            row["cohort_top"] = top
            got += 1
    return got


def load_tech_apply(distributions):
    """Read 四技申請 weighted 學測 screens as national GSAT percentiles."""
    rows = []
    source = data_path("tech-apply-cutoffs.tsv")
    for row in tsvio.read_rows(source):
        percentile = distributions.gsat_percentile(
            row["year"], row["subjects"], row["cutoff"]
        )
        top = None if percentile is None else 1.0 - percentile
        if top is None or top >= uac.NON_BINDING:
            continue
        row["system"], row["path"] = "tech", "tech_apply"
        uac.identify_department(row)
        row["seats"] = int(row["seats"])
        row["ceec_percentile"] = percentile
        rows.append(row)
    return rows


def naive_error(observations):
    """Disagreement if a percentile inside one exam is read as another's."""
    total = weight = 0.0
    for _, top_a, _, top_b, w in observations:
        total += w * abs(top_a - top_b)
        weight += w
    return 100.0 * total / weight if weight else 0.0


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

    print("\nfitted takers in each cohort-ability segment")
    header = "  " + f"{'exam':<9}{'observed':>11}" + "".join(
        f"{f'{100*k//pool_fit.bins}-{100*(k+1)//pool_fit.bins}%':>12}"
        for k in range(pool_fit.bins)
    )
    print(header)
    print("  " + "-" * (len(header) - 2))
    for exam in pool_fit.exams:
        counts = pool_fit.bin_counts(exam)
        print("  " + f"{exam:<9}{pool_fit.sizes[exam]:>11,.0f}"
              + "".join(f"{n:>12,.0f}" for n in counts))

    print("\nwhere a bar lands on the cohort, by exam")
    names = pool_fit.exams
    print("  " + f"{'top of takers':<20}" + "".join(f"{e:>12}" for e in names))
    for top in (0.01, 0.05, 0.10, 0.25, 0.50):
        cells = "".join(f"{100 * pool_fit.ability(e, top):>11.1f}%" for e in names)
        print("  " + f"top {100 * top:>4.0f}% of takers".ljust(20) + cells)


def source_rows():
    """Load only the admission rows that provide national percentile bars.

    Pool fitting and production ability scoring share these raw thresholds;
    neither passes through a separate department-ranking bridge.
    """
    distributions = ceec_score.ScoreDistributions.load(
        data_path("ceec-scores.tsv"), data_path("tongce-scores.tsv")
    )
    cohort = ceec_score.CohortPercentiles.load(data_path("ceec-scores.tsv"))
    uac_rows = list(uac.load("uac", distributions))
    tech_rows = list(uac.load("tech", distributions))
    uac.unify_spelling(uac_rows + tech_rows)
    known = {(r["year"], r["school"], r["dept"]) for r in uac_rows}
    apply_rows = uac.joinable(list(uac.load_apply(cohort)), known)
    star_rows = uac.joinable(list(uac.load_star(cohort=cohort)), known)
    star_eight_rows = uac.joinable(list(uac.load_star("eight", cohort)), known)
    tech_apply = load_tech_apply(distributions)
    rows = (uac_rows + tech_rows + apply_rows + star_rows
            + star_eight_rows + tech_apply)
    uac.unify_spelling(rows)
    return rows, len(apply_rows), len(tech_apply)


def observations(year=YEAR):
    """Pair departments admitting through two exams on their raw thresholds."""
    rows, _, _ = source_rows()
    rows = [row for row in rows if row["year"] == str(year)]
    apply_rows = sum(row["path"] == "apply" for row in rows)
    tech_apply = sum(row["path"] == "tech_apply" for row in rows)
    resolved = attach_apply_tops(rows)
    matched = model.matched(rows, exam_of, top_of)
    print(f"{resolved} of {apply_rows} 個人申請 bars read against the 學測 cohort",
          file=sys.stderr)
    print(f"{tech_apply} 四技申請 bars read against the 學測 cohort", file=sys.stderr)
    return rows, matched


def main():
    _, matched = observations()
    if not matched:
        print("no matched departments; nothing to fit", file=sys.stderr)
        return
    sizes = taker_counts()
    fitted, error = fit_pool(matched, sizes)
    report(fitted, matched, error)
    from pool.plot import draw

    written = draw(
        fitted, sizes, matched, error, naive_error(matched), YEAR
    )
    print(f"\nwrote {written}")


def subject_counts(year):
    """How many sat each subject of each exam, from the published distributions."""
    import csv

    totals = collections.defaultdict(lambda: collections.defaultdict(float))
    for name in ("ceec-scores.tsv", "tongce-scores.tsv"):
        with open(data_path(name), encoding="utf-8") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                if row["year"] != year or "、" in row["subject"]:
                    continue
                totals[row["exam"]][row["subject"]] += float(row["seats"])
    return totals


def taker_counts(year=YEAR):
    """How many sat each exam pool in `year`, from the published distributions."""
    totals = subject_counts(year)
    papers = totals.pop("tongce", {})
    # The most-sat subject is the closest thing to a headcount: everyone sits
    # 國文, but the science and language papers split the cohort.
    counts = {exam: max(subjects.values()) for exam, subjects in totals.items()}
    counts.update({pool: sum(papers.get(paper, 0.0) for paper in names)
                   for pool, names in tcte.POOL_PAPERS.items()})
    return counts


if __name__ == "__main__":
    main()
