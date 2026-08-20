"""Parse published 107 high-school entrance cutoffs.

The 107 college-admission cohort entered high school in 107. The first source
covers 基北區's named general high schools. It reports the 36-point CAP score,
which the district applies after the total and activity tie-breaks. These rows
measure selectivity, not each school's entrant distribution or school quality.
"""

import sys

from fetch.entry import SOURCES
from lib import tsvio
from lib.html_table import tables
from lib.paths import data_path, source_path


DISTRICT = "基北區"
YEAR = "107"
CAP_MAX = 36.0
CAPTION = f"{YEAR}{DISTRICT}高中錄取分數排序"


def table_after_caption(html, caption):
    """Find the table whose caption identifies a year and district."""
    marker = html.find(caption)
    start = html.rfind("<table", 0, marker)
    end = html.find("</table>", marker)
    if marker < 0 or start < 0 or end < 0:
        raise ValueError(f"missing table {caption}")
    found = tables(html[start:end + len("</table>")])
    if len(found) != 1:
        raise ValueError(f"could not isolate table {caption}")
    return found[0]


def parse_html(html):
    """Return the 107 基北 cutoff rows from the published historical table."""
    rows = table_after_caption(html, CAPTION)
    if rows[:1] != [["學校", "錄取分數"]]:
        raise ValueError("unexpected cutoff-table header")
    out = []
    for row in rows[1:]:
        if len(row) != 2:
            raise ValueError(f"unexpected cutoff row {row}")
        school, cutoff = row
        try:
            score = float(cutoff)
        except ValueError as e:
            raise ValueError(f"invalid cutoff {cutoff} for {school}") from e
        if not 0 <= score <= CAP_MAX:
            raise ValueError(f"cutoff out of range for {school}")
        out.append({
            "year": YEAR,
            "district": DISTRICT,
            "school": school,
            "cap_score": score,
            "cap_max": CAP_MAX,
            "source_quality": "third_party",
            "source": "tkb-jibei-107",
        })
    if not out:
        raise ValueError("no cutoff rows")
    return out


def main(out_path):
    source = source_path("entry", SOURCES["jibei-107-cutoffs"]["filename"])
    with open(source, encoding="utf-8") as f:
        rows = parse_html(f.read())
    written = tsvio.write_rows(out_path, rows)
    print(f"wrote {written} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(data_path("high-school-entry-cutoffs.tsv"))
