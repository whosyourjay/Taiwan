"""Every department's approved intake, split by the route that fills it.

表7-2 is the ministry's own allocation table, so it settles what a department
admits through each path in a year where our own seat tables disagree or say
nothing. The seat columns sit on a fixed grid, and the label rows above them
name each column once for the whole document.

原住民 seats are set as a share of the department's quota rather than a count,
so that one column carries a percentage and the school totals leave it blank.
"""

import collections
import sys

import pdfplumber

from lib import schoolname, tsvio
from lib.paths import data_path, source_path

SOURCE = "moe/moe-115-quota.pdf"
OUTPUT = "university-quotas.tsv"
YEAR = "115"
# Column centres in PDF points, read off the label rows. The spacing is even
# but drifts by a couple of points across the page, so the measured centres
# beat anything derived from a step.
GRID = (228.0, 250.0, 272.0, 294.0, 316.0, 338.0, 360.0, 382.0, 405.0, 427.0,
        449.0, 471.0, 493.0, 515.0, 537.5, 559.6, 581.7, 603.9, 626.0, 648.2,
        670.3, 692.4, 714.6, 738.1)
# One name per grid column. The first six carry the admission paths our seat
# tables already use, so they keep those spellings.
COLUMNS = (
    "approved_114", "total",
    "uac", "star", "apply", "tech_apply", "tech", "tech_skill",
    "athlete", "solo", "solo_school", "solo_dept", "special", "other",
    "extra_field",
    "extra_native_uac", "extra_native_star", "extra_native_apply",
    "extra_native_solo",
    "extra_security_apply", "extra_security_special",
    "extra_youth_apply", "extra_youth_tech",
    "extra_tech_skill",
)
# Columns inside 內含名額, which the published subtotal adds up.
INSIDE = COLUMNS[2:14]
# The one column published as a share of the quota rather than a count.
SHARE = "extra_native_uac"
SCHOOL_EDGE = 110.0
NAME_EDGE = 215.0
HEADER_DEPTH = 120.0
# Ordinary rows sit 7.3 points apart; the pieces of a wrapped row sit 3.
ROW_GAP = 5.0
# A row carrying seats fills nearly every column, so anything sparser is a
# footnote or a page number rather than a department.
FILLED = 20
TOTAL = "總計"
# A school with two campuses names each on its department rows and only the
# bare school on the total that covers both.


def lines(page):
    """Words on the page grouped into rows, each sorted left to right.

    A department name too long for its cell wraps onto two lines and the row
    centres its seats between them, so the three sit closer together than two
    ordinary rows do and belong to one another. A wrapped name reads down
    then across, so the words keep that order rather than a purely
    left-to-right one.
    """
    rows = collections.defaultdict(list)
    for word in page.extract_words():
        rows[round(word["top"], 1)].append(word)
    line = []
    previous = None
    for top in sorted(rows):
        if top < HEADER_DEPTH:
            continue
        if previous is not None and top - previous > ROW_GAP and line:
            yield sorted(line, key=lambda word: (word["top"], word["x0"]))
            line = []
        line += rows[top]
        previous = top
    if line:
        yield sorted(line, key=lambda word: (word["top"], word["x0"]))


def cell(word):
    """Which grid column a word sits in."""
    middle = (word["x0"] + word["x1"]) / 2
    return min(range(len(GRID)), key=lambda i: abs(GRID[i] - middle))


def split(line):
    """A row's school, its department words and its grid cells."""
    school, dept, cells = [], [], [""] * len(GRID)
    for word in line:
        if word["x0"] < SCHOOL_EDGE:
            school.append(word["text"])
        elif word["x0"] < NAME_EDGE:
            dept.append(word["text"])
        else:
            cells[cell(word)] = word["text"]
    return " ".join(school), "".join(dept), cells


def number(value):
    """A seat count, or None where the cell is blank or a share."""
    value = value.replace(",", "")
    return int(value) if value.isdigit() else None


def rows(pdf):
    """One row per department, plus the school totals for checking."""
    out = []
    for page in pdf.pages:
        for line in lines(page):
            school, dept, cells = split(line)
            if not school or not dept:
                continue
            if sum(bool(value) for value in cells) < FILLED:
                continue
            row = {"year": YEAR, "school": school, "dept": dept}
            for name, value in zip(COLUMNS, cells):
                row[name] = value if name == SHARE else number(value)
            out.append(row)
    return out


def checked(found):
    """Drop the school totals after testing them against their departments."""
    groups = collections.defaultdict(list)
    for row in found:
        groups[schoolname.without_campus(row["school"])].append(row)
    total_ids = set()
    compare = ("total",) + INSIDE
    for school, group in groups.items():
        exact = [row for row in group if row["dept"] == TOTAL]
        candidates = exact
        if not candidates:
            candidates = [
                row for row in group
                if all((row[name] or 0) == sum(
                    (other[name] or 0) for other in group if other is not row
                ) for name in compare)
            ]
        if not candidates or (not exact and len(candidates) != 1):
            raise ValueError(f"{school}: found {len(candidates)} school totals")
        total_ids.update(id(row) for row in candidates)
    totals = collections.defaultdict(collections.Counter)
    for row in found:
        if id(row) not in total_ids:
            continue
        key = schoolname.without_campus(row["school"])
        for name in COLUMNS[1:]:
            if name != SHARE and row[name]:
                totals[key][name] += row[name]
    summed = collections.defaultdict(collections.Counter)
    for row in found:
        if id(row) in total_ids:
            continue
        key = schoolname.without_campus(row["school"])
        for name in COLUMNS[1:]:
            if name != SHARE and row[name]:
                summed[key][name] += row[name]
    for school, total in totals.items():
        for name in COLUMNS[1:]:
            if name != SHARE and total[name] != summed[school][name]:
                raise ValueError(
                    f"{school} {name}: total {total[name]}"
                    f" against {summed[school][name]} from its departments")
    return [row for row in found if id(row) not in total_ids]


def report(found, out=sys.stderr):
    """Coverage and the national route mix."""
    schools = {row["school"] for row in found}
    print(f"{len(found)} departments across {len(schools)} schools", file=out)
    seats = {name: sum(row[name] or 0 for row in found) for name in INSIDE}
    total = sum(seats.values())
    for name, count in sorted(seats.items(), key=lambda item: -item[1]):
        if count:
            print(f"  {name:<14}{count:>8,}{100 * count / total:>7.1f}%", file=out)


def main():
    with pdfplumber.open(source_path(SOURCE)) as pdf:
        found = checked(rows(pdf))
    report(found)
    written = tsvio.write_rows(data_path(OUTPUT), found)
    print(f"wrote {written} rows to {data_path(OUTPUT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
