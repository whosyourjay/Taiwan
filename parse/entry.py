"""Parse published high-school entrance cutoffs.

The 110 college-admission cohort entered high school in 107, which one source
covers for 基北區 on its 36-point CAP score. A second gives six districts at
once, each on the total its own 超額比序 runs, so those scores order schools
inside a district and need that district's conversion before they compare
across districts. Every row measures selectivity, not who ends up enrolling.
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
FALLING_SOURCE = "educatorfocus-114-cutoffs"
FALLING_YEAR = "114"
FALLING_DISTRICTS = ("基北區", "桃連區", "竹苗區", "中投區", "臺南區", "高雄區")


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


def paired(rows):
    """Split a table printed as two school-and-score columns side by side."""
    for row in rows:
        for index in range(0, len(row) - 1, 2):
            school, cutoff = row[index].strip(), row[index + 1].strip()
            if school and cutoff:
                yield school, cutoff


def parse_falling(html):
    """Cutoff rows for every district the 114 落點 tables cover.

    Districts score their own 超額比序 on their own totals, so only 基北's is the
    36-point CAP score. The rest keep their published number and name no maximum
    until each district's conversion is read.
    """
    found = tables(html)
    if len(found) != len(FALLING_DISTRICTS):
        raise ValueError(f"expected {len(FALLING_DISTRICTS)} district tables,"
                         f" found {len(found)}")
    out = []
    for district, rows in zip(FALLING_DISTRICTS, found):
        if rows[0][:2] != ["學校", "錄取分數"]:
            raise ValueError(f"unexpected header for {district}: {rows[0]}")
        for school, cutoff in paired(rows[1:]):
            out.append({
                "year": FALLING_YEAR,
                "district": district,
                "school": school,
                "cap_score": float(cutoff),
                "cap_max": CAP_MAX if district == DISTRICT else "",
                "source_quality": "third_party",
                "source": FALLING_SOURCE,
            })
    return out


def main(out_path):
    source = source_path("entry", SOURCES["jibei-107-cutoffs"]["filename"])
    with open(source, encoding="utf-8") as f:
        rows = parse_html(f.read())
    falling = source_path("entry", SOURCES[FALLING_SOURCE]["filename"])
    with open(falling, encoding="utf-8") as f:
        rows += parse_falling(f.read())
    written = tsvio.write_rows(out_path, rows)
    print(f"wrote {written} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(data_path("high-school-entry-cutoffs.tsv"))
