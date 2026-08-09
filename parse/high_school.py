"""Parse high-school reports of graduates' university destinations.

The 110 北一女 table names domestic universities with at least ten students,
then accounts for every remaining domestic and overseas destination in grouped
rows. `destination_type=university` gives the observed matrix cells; the other
types preserve the censored mass instead of turning unlisted universities into
zeroes.
"""

import re
import sys

from fetch.high_school import SOURCES
from lib import tsvio
from lib.paths import path
from parse.uac import pdf_text


LEFT_UNIVERSITY = re.compile(
    r"^ {0,5}(\S.*?(?:大學|學院))\s{2,}(\d+)(?:\s|$)"
)
FOREIGN_ROW = re.compile(
    r"^ {0,5}(美國|中國|香港|其他\(國外大學\))\s{2,}(\d+)(?:\s|$)",
    re.M,
)


def _number(text, pattern, label):
    match = re.search(pattern, text)
    if not match:
        raise ValueError(f"missing {label}")
    return int(match.group(1))


def _table_text(text):
    marker = text.find("畢業生大學校系錄取人數統計表")
    if marker < 0:
        raise ValueError("missing destination table")
    start = text.rfind("\n", 0, marker) + 1
    end = text.find("畢業生大學錄取管道人數統計表", marker)
    if end < 0:
        raise ValueError("missing destination table")
    return text[start:end]


def _university_rows(table):
    start = re.search(r"列出錄取\s*\d+\s*人以上學校", table)
    end = table.find("其他(國內學校)")
    if not start or end < 0:
        raise ValueError("missing named-university section")
    rows = []
    for line in table[start.end():end].splitlines():
        match = LEFT_UNIVERSITY.match(line)
        if match:
            rows.append((match.group(1).strip(), int(match.group(2))))
    if not rows:
        raise ValueError("no named universities")
    return rows


def parse_text(text, high_school):
    """Return destination rows after checking every printed subtotal."""
    table = _table_text(text)
    year = re.search(r"(\d+)\s*學年度畢業生大學校系錄取人數統計表", table)
    date = re.search(r"統計表\((\d+)\.(\d+)\.(\d+)\)", table)
    domestic_floor = _number(
        table, r"列出錄取\s*(\d+)\s*人以上學校", "domestic reporting floor"
    )
    foreign_floor = _number(
        table,
        r"列出錄取\s*(\d+)\s*人以上國家/地區",
        "foreign reporting floor",
    )
    if not year or not date:
        raise ValueError("missing year or source date")

    destinations = [
        (university, "university", students, domestic_floor)
        for university, students in _university_rows(table)
    ]
    other_domestic = _number(
        table, r"其他\(國內學校\)\s+(\d+)", "other domestic"
    )
    destinations.append(
        ("其他(國內學校)", "domestic_other", other_domestic, domestic_floor)
    )
    for name, students in FOREIGN_ROW.findall(table):
        kind = "foreign_other" if name.startswith("其他") else "foreign_country"
        destinations.append((name, kind, int(students), foreign_floor))

    domestic_total = _number(table, r"國內學校小計\s+(\d+)", "domestic total")
    foreign_total = _number(table, r"國外學校小計\s+(\d+)", "foreign total")
    total = _number(table, r"國內外學校總計\s+(\d+)", "destination total")
    graduates = _number(
        table, rf"{year.group(1)}\s*高三應屆畢業生總人數\s+(\d+)", "graduates"
    )
    named_total = sum(n for _, kind, n, _ in destinations if kind == "university")
    foreign_sum = sum(
        n for _, kind, n, _ in destinations if kind.startswith("foreign")
    )
    if named_total + other_domestic != domestic_total:
        raise ValueError("named and other domestic rows do not match subtotal")
    if foreign_sum != foreign_total or domestic_total + foreign_total != total:
        raise ValueError("destination rows do not match printed totals")
    if total > graduates:
        raise ValueError("destinations exceed graduating class")

    source_date = f"{date.group(1)}-{int(date.group(2)):02d}-{int(date.group(3)):02d}"
    return [
        {
            "year": year.group(1),
            "high_school": high_school,
            "destination": destination,
            "destination_type": kind,
            "students": students,
            "reporting_floor": reporting_floor,
            "graduates": graduates,
            "source_date": source_date,
        }
        for destination, kind, students, reporting_floor in destinations
    ]


def parse(source):
    return parse_text(pdf_text(source["path"]), source["high_school"])


def main(out_path):
    rows = []
    for year, source in SOURCES.items():
        source = {**source, "path": path("high-school", source["filename"])}
        got = parse(source)
        named = sum(r["students"] for r in got if r["destination_type"] == "university")
        total = sum(r["students"] for r in got)
        print(f"{year} {source['high_school']}: {named}/{total} named", file=sys.stderr)
        rows.extend(got)
    written = tsvio.write_rows(out_path, rows)
    print(f"wrote {written} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(path("high-school-destinations.tsv"))
