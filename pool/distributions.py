#!/usr/bin/env python3
"""Write score-bucket pieces for every measured admission allocation."""

if __package__ in (None, ""):
    import _bootstrap  # noqa: F401

import numpy as np

from lib import tsvio
from lib.paths import data_path, ranking_path
from pool import ability, fit as pool_fit
from rank import ceec_score


FIELDS = (
    "school", "dept", "application_group", "path", "year", "exam",
    "source_scale", "ability_lower", "ability_upper", "bucket_candidates",
    "seats", "bucket_basis",
)


def filled(buckets, cutoff, seats):
    """Take seats from the first qualifying score bucket and then higher ones."""
    start = next((index for index, bucket in enumerate(buckets)
                  if bucket[2] >= float(cutoff)), None)
    if start is None:
        return []
    out, remaining = [], float(seats)
    for low, high, _, candidates in buckets[start:]:
        take = min(remaining, candidates)
        if take > 0:
            out.append((low, high, candidates, take))
            remaining -= take
        if remaining <= 1e-9:
            break
    return out if remaining <= 1e-9 else []


def mapped(spline, low, high):
    values = [float(np.clip(spline(point), 0.0, 1.0)) for point in (low, high)]
    return 100.0 * min(values), 100.0 * max(values)


def formula_pieces(row, exam, distributions, splines, sizes):
    if row["path"] == "uac":
        buckets = distributions.formula_buckets(
            row["year"], row["subjects"], "uac"
        )
    elif row["path"] == "tech":
        buckets = distributions.formula_buckets(
            row["year"], row["subjects"], "tongce", row["group"]
        )
    else:
        buckets = distributions.formula_buckets(
            row["year"], row["subjects"], "gsat"
        )
    population = sizes.get(exam)
    if not buckets or not population or exam not in splines:
        return []
    buckets = [(low, high, score, (high - low) * population)
               for low, high, score, _ in buckets]
    return [(mapped(splines[exam], low, high), candidates, take,
             "equal-quantile composite")
            for low, high, candidates, take in filled(
                buckets, row["cutoff"], row["seats"]
            )]


def exact_gsat_pieces(row, cohort, splines, label, cutoff):
    buckets = cohort.score_buckets(row["year"], label)
    if not buckets or "gsat" not in splines:
        return []
    return [(mapped(splines["gsat"], low, high), candidates, take,
             "published GSAT score")
            for low, high, candidates, take in filled(
                buckets, cutoff, row["seats"]
            )]


def star_pieces(row, cohort, splines, assessment):
    class_low = float(row["class_pct"]) / 100.0
    class_high = min(1.0, class_low + 0.01)
    class_ability = (class_low + class_high) / 2
    gates = []
    for label, level in ceec_score.GATE.findall(row.get("gates", "")):
        buckets = cohort.score_buckets(row["year"], label)
        selected = filled(buckets, level, row["seats"])
        if not selected or "gsat" not in splines:
            continue
        low, high, _, _ = selected[0]
        gate_ability = sum(mapped(splines["gsat"], low, high)) / 200.0
        gates.append((gate_ability, label, level))
    if gates and max(gates)[0] > class_ability:
        _, label, level = max(gates)
        return exact_gsat_pieces(row, cohort, splines, label, level)
    candidates = assessment * (class_high - class_low)
    return [((100.0 * class_low, 100.0 * class_high), candidates,
             float(row["seats"]), "within-school rank")]


def allocation_pieces(row, exam, distributions, cohort, splines, sizes,
                      assessment):
    if row["path"] in ("uac", "tech", "tech_apply"):
        return formula_pieces(row, pool_fit.exam_of(row), distributions,
                              splines, sizes)
    if row["path"] == "apply":
        return exact_gsat_pieces(
            row, cohort, splines, row["cut_label"], row["cut_level"]
        )
    if row["path"] in (ability.STAR, ability.STAR_EIGHT):
        return star_pieces(row, cohort, splines, assessment)
    return []


def rows():
    source, splines = ability.curves()
    distributions = ceec_score.ScoreDistributions.load(
        data_path("ceec-scores.tsv"), data_path("tongce-scores.tsv")
    )
    cohort = ceec_score.CohortPercentiles.load(data_path("ceec-scores.tsv"))
    sizes = pool_fit.taker_counts()
    assessment = ability.tiling.assessment_size(pool_fit.YEAR)
    for row, exam, _, _ in ability.read(source, splines):
        for (low, high), candidates, seats, basis in allocation_pieces(
                row, exam, distributions, cohort, splines, sizes, assessment):
            yield {
                "school": row["school"], "dept": row["dept"],
                "application_group": row["application_group"],
                "path": row["path"], "year": row["year"], "exam": exam,
                "source_scale": ("cohort" if basis == "within-school rank"
                                 else "test_taker"),
                "ability_lower": round(low, 6), "ability_upper": round(high, 6),
                "bucket_candidates": round(candidates, 6),
                "seats": round(seats, 6), "bucket_basis": basis,
            }


def main():
    found = list(rows())
    target = ranking_path("ability-intervals.tsv")
    print(f"{tsvio.write_rows(target, found)} score-bucket pieces -> {target}")


if __name__ == "__main__":
    main()
