"""Export the last same-cohort GSAT subject and five-subject histograms."""

import argparse
import sys

from lib import tsvio
from lib.paths import data_path


YEAR = "107"
EXAM = "gsat"
TOTAL = "國文、英文、數學、社會、自然"
SUBJECTS = TOTAL.split("、")


def source_rows(year=YEAR):
    return [row for row in tsvio.read_rows(data_path("ceec-scores.tsv"))
            if row["year"] == str(year) and row["exam"] == EXAM]


def exported_rows(rows, year=YEAR):
    by_subject = {}
    for row in rows:
        by_subject.setdefault(row["subject"], []).append(row)
    missing = [subject for subject in (*SUBJECTS, TOTAL) if subject not in by_subject]
    if missing:
        raise ValueError(f"{year}: missing GSAT distributions: {', '.join(missing)}")
    candidates = sum(float(row["seats"]) for row in by_subject[TOTAL])
    common = {"exam": "GSAT", "year": str(year), "pool": "five-subject cohort"}
    subject_rows = [
        {**common, "subject": subject, "score": row["score"],
         "count": row["seats"]}
        for subject in SUBJECTS for row in by_subject[subject]
    ]
    formula_rows = [
        {**common, "formula": "five-subject total", "subject": subject,
         "weight": 1, "candidates": candidates}
        for subject in SUBJECTS
    ]
    total_rows = [
        {**common, "formula": "five-subject total", "total_score": row["score"],
         "count": row["seats"]}
        for row in by_subject[TOTAL]
    ]
    return subject_rows, formula_rows, total_rows


def main(year=YEAR):
    tables = exported_rows(source_rows(year), year)
    names = ("joint-score-subjects.tsv", "joint-score-formulas.tsv",
             "joint-score-totals.tsv")
    for name, rows in zip(names, tables):
        path = data_path(name)
        written = tsvio.write_rows(path, rows)
        print(f"wrote {written:,} rows to {path}", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", default=YEAR)
    main(parser.parse_args().year)
