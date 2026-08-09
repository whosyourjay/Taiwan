"""Parse official national CAP achievement-category distributions."""

import re
import sys

from fetch.entry import SOURCES
from lib import tsvio
from lib.html_table import tables
from lib.paths import data_path, path


CATEGORY = re.compile(r"^\d+A\d+B\d+C$")
YEAR = "107"


def parse_html(html):
    """Return national counts for five-subject A/B/C achievement categories."""
    source_table = next(
        (table for table in tables(html) if any(row[:1] == ["5A0B0C"] for row in table)),
        None,
    )
    if not source_table:
        raise ValueError("missing CAP achievement-category table")
    rows = []
    for row in source_table:
        if len(row) < 3 or not CATEGORY.match(row[0]):
            continue
        rows.append({
            "year": YEAR,
            "category": row[0],
            "students": int(row[1]),
            "pct": float(row[2].removesuffix("%")),
        })
    if not rows:
        raise ValueError("no CAP achievement categories")
    return rows


def main(out_path):
    source = path("entry", SOURCES["cap-107-statistics"]["filename"])
    with open(source, encoding="utf-8") as f:
        rows = parse_html(f.read())
    written = tsvio.write_rows(out_path, rows)
    print(f"wrote {written} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(data_path("cap-grade-distributions.tsv"))
