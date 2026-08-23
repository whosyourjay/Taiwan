"""Parse the ministry's roster of 免試入學 committee sites.

Every 就學區 admits through the same platform on a host of its own, so this
roster is the entry point for anything the districts publish per school.
"""

import re
import subprocess
import sys

from lib import tsvio
from lib.paths import data_path, source_path

SOURCE = "moe-115-entry-districts.pdf"
OUTPUT = "entry-districts.tsv"
YEAR = "115"
ROW = re.compile(r"^\s*(\d+)\s+(\S+區)\s+(.*?)\s*(https://\S+?)/?\s*$")


def text(path):
    """The layout-preserving text of a PDF."""
    found = subprocess.run(["pdftotext", "-layout", path, "-"],
                           stdout=subprocess.PIPE, check=True)
    return found.stdout.decode("utf-8", "replace")


def rows(body):
    """One row per district, taking a wrapped chair school from the line above."""
    lines = body.splitlines()
    out = []
    for index, line in enumerate(lines):
        found = ROW.match(line)
        if not found:
            continue
        number, district, school, host = found.groups()
        if not school:
            # A long chair school wraps around its own row, above and below it.
            tail = lines[index + 1].strip() if index + 1 < len(lines) else ""
            school = lines[index - 1].strip() + ("" if ROW.match(tail) else tail)
        out.append({
            "year": YEAR,
            "number": int(number),
            "district": district,
            "chair_school": school,
            "host": host,
        })
    return sorted(out, key=lambda row: row["number"])


def main():
    found = rows(text(source_path("entry", SOURCE)))
    if len(found) != 15:
        raise ValueError(f"expected 15 districts, parsed {len(found)}")
    written = tsvio.write_rows(data_path(OUTPUT), found)
    print(f"wrote {written} rows to {data_path(OUTPUT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
