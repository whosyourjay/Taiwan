"""Parse UAC's post-return 分發入學 seats by program.

These counts include seats returned by earlier admission routes, so they are
the final UAC capacity rather than the ministry's initial route allocation.
"""

import glob
import os
import re
import sys

import openpyxl

from lib import tsvio
from lib.paths import data_path, source_path


SOURCE_PATTERN = "uac/*-count.xlsx"
OUTPUT = "uac-seats.tsv"
HEADER_ALIASES = {
    "school": ("學校名稱",),
    "dept": ("學系組名稱",),
    "code": ("系組代碼", "校系代碼"),
    "seats": ("回流後分發入學總名額", "回流後考試分發總名額"),
}


def clean(value):
    return re.sub(r"\s+", "", str(value or ""))


def code_of(value):
    value = str(value or "").strip()
    if value.endswith(".0") and value[:-2].isdigit():
        value = value[:-2]
    return value.zfill(4) if value.isdigit() else value


def header_indices(values):
    headers = [clean(value) for value in values]
    indices = {}
    for field, aliases in HEADER_ALIASES.items():
        found = [headers.index(alias) for alias in aliases if alias in headers]
        if len(found) != 1:
            raise ValueError(f"unexpected UAC seat headers: {tuple(headers)}")
        indices[field] = found[0]
    return indices


def rows(source, year):
    """Return coded program rows and the workbook's published grand total."""
    book = openpyxl.load_workbook(source, read_only=True, data_only=True)
    values = book.worksheets[0].iter_rows(values_only=True)
    columns = header_indices(next(values))
    found, published = [], None
    for values in values:
        school = values[columns["school"]]
        dept = values[columns["dept"]]
        code = values[columns["code"]]
        seats = values[columns["seats"]]
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


def source_files():
    return sorted(glob.glob(source_path(SOURCE_PATTERN)))


def main(out_path=None):
    found = []
    for source in source_files():
        year = os.path.basename(source).split("-", 1)[0]
        annual = checked(*rows(source, year))
        print(f"{year}: {len(annual)} programs, "
              f"{sum(row['seats'] for row in annual):,} seats", file=sys.stderr)
        found.extend(annual)
    target = out_path or data_path(OUTPUT)
    written = tsvio.write_rows(target, found)
    print(f"wrote {written} rows to {target}", file=sys.stderr)


if __name__ == "__main__":
    main()
