"""Mark 個人申請 PNG rows by whether they can support a 分發 join."""

import collections

from lib import tsvio
from lib.paths import data_path
from rank import ceec_score, uac


def row_id(row):
    """The program code identifies one row inside one annual PNG collection."""
    return row["year"], row["college_code"], row["dept_code"]


def classify(row, usable, matched, uac_schools):
    """``(status, detail)`` without treating an unknown school as no 分發."""
    key = row_id(row)
    college = row["college"].strip()
    if key in matched:
        return "matched_fenfa", matched[key]
    if not college:
        return "unidentified_school_png", "college name missing from apply/colleges.tsv"
    if (row["year"], college) not in uac_schools:
        return "no_fenfa_school", "school has no 分發入學 row that year"
    if key in usable:
        return "unmatched_png", "usable screen; no unambiguous department join"
    return "unscored_png", "screen is blank, invalid, or non-binding"


def audit_rows():
    """Every parsed 個申 row, retaining its source fields plus join status."""
    scores = data_path("ceec-scores.tsv")
    cohort = ceec_score.CohortPercentiles.load(scores)
    distributions = ceec_score.ScoreDistributions.load(
        scores, data_path("tongce-scores.tsv")
    )
    uac_rows = list(uac.load("uac", distributions))
    known = {(row["year"], row["school"], row["dept"]) for row in uac_rows}
    usable_rows = list(uac.load_apply(cohort))
    matched_rows = uac.joinable(usable_rows, known)
    usable = {row_id(row) for row in usable_rows}
    matched = {row_id(row): row["dept"] for row in matched_rows}
    uac_schools = {(row["year"], row["school"]) for row in uac_rows}
    out = []
    for row in tsvio.read_rows(data_path("apply-cutoffs.tsv")):
        status, detail = classify(row, usable, matched, uac_schools)
        out.append({
            **row,
            "png": f"apply/{row['year']}-{row['college_code']}.png",
            "fenfa_status": status,
            "fenfa_detail": detail,
        })
    return out


def main():
    rows = audit_rows()
    written = tsvio.write_rows(data_path("apply-fenfa-audit.tsv"), rows)
    counts = collections.Counter(row["fenfa_status"] for row in rows)
    print(
        f"wrote {written} rows: "
        + ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    )


if __name__ == "__main__":
    main()
