"""Parse UAC's post-return 分發入學 seats by program.

These counts include seats returned by earlier admission routes, so they are
the final UAC capacity rather than the ministry's initial route allocation.
"""

import re
import sys

import openpyxl

from lib import tsvio
from lib.paths import data_path, source_path


SOURCE = "uac/115-count.xlsx"
OUTPUT = "uac-seats.tsv"
YEAR = "115"
HEADERS = ("序號", "學校名稱", "學系組名稱", "系組代碼", "回流後分發入學總名額")


def clean(value):
    return re.sub(r"\s+", "", str(value or ""))


def code_of(value):
    value = str(value or "").strip()
    if value.endswith(".0") and value[:-2].isdigit():
        value = value[:-2]
    return value.zfill(4) if value.isdigit() else value


def rows(source, year=YEAR):
    """Return coded program rows and the workbook's published grand total."""
    book = openpyxl.load_workbook(source, read_only=True, data_only=True)
    values = book.worksheets[0].iter_rows(values_only=True)
    headers = tuple(clean(value) for value in next(values))
    if headers != HEADERS:
        raise ValueError(f"unexpected UAC seat headers: {headers}")
    found, published = [], None
    for _, school, dept, code, seats in values:
        code = code_of(code)
        if code:
            found.append({
                "year": str(year), "code": code,
                "school": str(school or "").strip(),
                "dept": str(dept or "").strip(), "seats": int(seats or 0),
            })
        elif clean(school) == "總計":
            published = int(seats)
    book.close()
    return found, published


def checked(found, published):
    """Reconcile program rows against the workbook total."""
    codes = [row["code"] for row in found]
    if len(codes) != len(set(codes)):
        raise ValueError("duplicate UAC program codes")
    if any(not row["school"] or not row["dept"] or row["seats"] < 0
           for row in found):
        raise ValueError("invalid UAC program row")
    total = sum(row["seats"] for row in found)
    if published is None or total != published:
        raise ValueError(f"UAC program seats {total:,} != published {published}")
    return found


def main(out_path=None):
    found = checked(*rows(source_path(SOURCE)))
    target = out_path or data_path(OUTPUT)
    written = tsvio.write_rows(target, found)
    print(f"wrote {written} rows ({sum(row['seats'] for row in found):,} seats) "
          f"to {target}", file=sys.stderr)


if __name__ == "__main__":
    main()
