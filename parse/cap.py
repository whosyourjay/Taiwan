"""Parse official national CAP achievement-category distributions.

The same page carries three tables. Two of them describe the five-subject
category — its size, and how 寫作測驗 級分 splits inside it. The third gives
each subject's plus-mark shares, which is what separates an A++ from a bare A
and so what makes the 36-point 基北 entry score readable at all.
"""

import sys

from fetch.entry import SOURCES
from lib import tsvio
from lib.cap import CATEGORY, MARKS, WRITING
from lib.html_table import tables
from lib.paths import data_path, source_path


YEAR = "107"
GROUPS = ("精熟", "基礎", "待加強")
def find_table(all_tables, wanted):
    """The first table holding a cell that answers `wanted`."""
    for table in all_tables:
        for row in table:
            if any(wanted(cell) for cell in row):
                return table
    raise ValueError("missing CAP table")


def percent(cell):
    return float(cell.removesuffix("%"))


def categories(all_tables):
    """National counts for the five-subject A/B/C achievement categories."""
    rows = []
    for row in find_table(all_tables, lambda cell: cell == "5A0B0C"):
        if len(row) < 3 or not CATEGORY.match(row[0]):
            continue
        rows.append({
            "year": YEAR,
            "category": row[0],
            "students": int(row[1]),
            "pct": percent(row[2]),
        })
    if not rows:
        raise ValueError("no CAP achievement categories")
    return rows


def subject_marks(all_tables):
    """Each subject's share at every plus-mark, from A++ down to C.

    A group's own row prints the group total beside the first mark, so those
    rows arrive with two numbers per subject and the totals drop out.
    """
    table = find_table(all_tables, lambda cell: cell == "A++")
    subjects = [cell for cell in table[0] if cell]
    rows = []
    for row in table[1:]:
        cells = row[1:] if row[0] in GROUPS else list(row)
        mark, values = cells[0], cells[1:]
        if mark not in MARKS:
            continue
        if len(values) == 2 * len(subjects):
            values = values[1::2]
        if len(values) != len(subjects):
            raise ValueError(f"unexpected width for mark {mark}")
        rows.extend({"year": YEAR, "subject": subject, "mark": mark,
                     "pct": percent(value)}
                    for subject, value in zip(subjects, values))
    if len(rows) != len(MARKS) * len(subjects):
        raise ValueError("incomplete CAP plus-mark table")
    return rows


def writing_levels(all_tables):
    """寫作測驗 級分 counts inside each five-subject category."""
    rows = []
    for row in find_table(all_tables, lambda cell: cell == "六級分"):
        if len(row) < 3 + 3 * len(WRITING) or not CATEGORY.match(row[0]):
            continue
        for index, level in enumerate(WRITING):
            students, _, share = row[3 + 3 * index:6 + 3 * index]
            rows.append({
                "year": YEAR,
                "category": row[0],
                "writing": level,
                "students": int(students),
                "pct": percent(share),
            })
    if not rows:
        raise ValueError("no CAP writing-level rows")
    return rows


OUTPUTS = (
    ("cap-grade-distributions.tsv", categories),
    ("cap-subject-marks.tsv", subject_marks),
    ("cap-writing-levels.tsv", writing_levels),
)


def main():
    source = source_path("entry", SOURCES["cap-107-statistics"]["filename"])
    with open(source, encoding="utf-8") as f:
        all_tables = tables(f.read())
    for name, builder in OUTPUTS:
        target = data_path(name)
        written = tsvio.write_rows(target, builder(all_tables))
        print(f"wrote {written} rows to {target}", file=sys.stderr)


if __name__ == "__main__":
    main()
