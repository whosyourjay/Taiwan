"""Every high school's roll and graduating cohort, from the ministry's own file.

繁星 quotes a class rank as a whole percent rounded up, so a school's size caps
how fine that rank can be: nobody in a cohort of fifty can be inside the top 1%,
because the best of them rounds to 2%. The cohort size is what makes that
readable, and it is the only thing this table is for.
"""

import csv
import sys

from lib import tsvio
from lib.paths import data_path, source_path

SOURCE = "moe-high-school-base.csv"
OUTPUT = "high-school-sizes.tsv"
COLUMNS = ("學生數男", "學生數女", "上學年畢業生數男", "上學年畢業生數女")


def rows(reader):
    """One row per school and year, carrying the roll and last year's leavers."""
    out = []
    for row in reader:
        students = int(row[COLUMNS[0]]) + int(row[COLUMNS[1]])
        graduates = int(row[COLUMNS[2]]) + int(row[COLUMNS[3]])
        if not students and not graduates:
            continue
        out.append({
            "year": row["學年度"],
            "school_code": row["學校代碼"],
            "school": row["學校名稱"],
            "county": row["縣市名稱"],
            "classes": int(row["班級數"]),
            "students": students,
            "graduates": graduates,
        })
    return out


def main():
    with open(source_path("moe", SOURCE), encoding="utf-8-sig") as handle:
        found = rows(csv.DictReader(handle))
    written = tsvio.write_rows(data_path(OUTPUT), found)
    print(f"wrote {written} rows to {data_path(OUTPUT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
