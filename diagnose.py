"""Print the per-path score behind a sample of departments, for eyeballing.

The rankings average every admission path into one number per department, which
hides the thing most worth checking: whether the paths agree about a department
once they are on the shared axis. This prints them side by side.

A column is the score that path alone implies, 0-100 over admitted seats
nationally. `spread` is the gap between the highest and lowest path present, so
a large value means the bridges disagree about that department.

Schools are fixed rather than chosen by rank, to keep one of each kind in view:
繁星 and 個人申請 were only collected for 8 schools, and 統測 reaches a
科技大學 that 分發入學 never touches.
"""

import collections
import contextlib
import sys
import unicodedata

import rank_uac

PATHS = rank_uac.PATHS
DEPTS_PER_SCHOOL = 5
# Wide enough for the longest path name, so a header never runs into its neighbour.
COLUMN = max(8, max(len(path) for path in PATHS) + 1)

# Always shown where a school has them, since the two hardest departments in the
# country are the ones worth watching a bridge against.
PINNED = ("醫學系", "牙醫學系")

# Which exam a path's raw scale actually comes from.
EXAMS = {
    "uac": "指考/分科測驗",
    "tech": "統測",
    "star": "學測 (在校排名)",
    "apply": "學測 (篩選級分)",
}
# The year every school was collected for. Other years hold 8 schools of 繁星
# and 個人申請, too narrow a slice to read an endpoint off.
SCALE_YEAR = "110"

SCHOOLS = [
    ("國立臺灣大學", "comprehensive flagship"),
    ("國立陽明交通大學", "medical + comprehensive"),
    ("臺北醫學大學", "medical"),
    ("國立宜蘭大學", "dual system: 分發入學 + 統測"),
    ("國立臺灣科技大學", "科技大學"),
]


def width(text):
    """Display columns the text occupies, counting CJK as two."""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def pad(text, n):
    """Left-justify to n display columns, truncating if it does not fit."""
    while width(text) > n:
        text = text[:-1]
    return text + " " * (n - width(text))


def by_path(rows):
    """(school, dept) -> {path: (score, seats per year)}."""
    cells = collections.defaultdict(lambda: collections.defaultdict(list))
    for row in rows:
        cells[(row["school"], row["dept"])][row["path"]].append(row)
    out = {}
    for key, paths in cells.items():
        out[key] = {
            path: (rank_uac.wmean(group, "score"),
                   sum(r["seats"] for r in group) / len({r["year"] for r in group}))
            for path, group in paths.items()
        }
    return out


def scale_endpoints(rows, year, field):
    """The span of each path's input that year, and where it lands on `field`.

    A curved path spans 0-100 by construction; an absolute one spans whatever
    the cohort gave it, so both ends are reported as observed rather than
    extrapolated to a nominal 0 and 100. What the comparison shows is how much
    of the national axis each exam is mapped onto.
    """
    out = {}
    for path in PATHS:
        group = [r for r in rows if r["path"] == path and r["year"] == year]
        if len(group) < 2:
            continue
        low = min(group, key=lambda r: r["pct"])
        high = max(group, key=lambda r: r["pct"])
        out[path] = (low["pct"], high["pct"], low[field], high[field])
    return out


def coverage(rows, year):
    """Official, observed and unranked seats per path for one year."""
    totals = rank_uac.load_admission_totals()
    observed = collections.Counter()
    for row in rows:
        observed[(row["year"], row["path"])] += row["seats"]
    out = []
    for (y, path), official in sorted(totals.items()):
        if y == year:
            out.append((path, official, observed[(y, path)]))
    return out


def pick(table, school):
    """The school's departments: pinned first, then most paths, then intake."""
    depts = [(dept, paths) for (s, dept), paths in table.items() if s == school]
    pinned = sorted((d for d in depts if d[0] in PINNED),
                    key=lambda d: PINNED.index(d[0]))
    rest = sorted((d for d in depts if d[0] not in PINNED),
                  key=lambda d: (-len(d[1]), -sum(s for _, s in d[1].values())))
    return (pinned + rest)[:DEPTS_PER_SCHOOL]


def main():
    # The pipeline reports its bridge fits on stdout; keep that off the table.
    with contextlib.redirect_stdout(sys.stderr):
        rows = rank_uac.build_rows()
    table = by_path(rows)

    head = pad("department", 26) + f"{'seats/yr':>9}"
    head += "".join(f"{p:>{COLUMN}}" for p in PATHS) + f"{'spread':>9}"
    for school, kind in SCHOOLS:
        depts = pick(table, school)
        print(f"\n{school}  ({kind})")
        if not depts:
            print("  no rows")
            continue
        print("  " + head)
        print("  " + "-" * width(head))
        for dept, paths in depts:
            seats = sum(s for _, s in paths.values())
            line = "  " + pad(dept, 26) + f"{seats:>9.1f}"
            for path in PATHS:
                line += (f"{paths[path][0]:>{COLUMN}.1f}" if path in paths
                         else f"{'-':>{COLUMN}}")
            scores = [v[0] for v in paths.values()]
            gap = max(scores) - min(scores)
            line += f"{gap:>9.1f}" if len(scores) > 1 else f"{'':>9}"
            print(line)

    print("\nScores are 0-100 over admitted seats nationally, so they are"
          " comparable across paths.")
    print("A blank spread means only one path was collected for that department.")
    print(f"{'/'.join(PINNED)} score under star_eight rather than star: 第八類學群"
          " publishes a 通過篩選")
    print("bar ahead of its 甄試, so it keeps its own path and weighs by quota.")

    print(f"\nSeat coverage, year {SCALE_YEAR}")
    head = pad("path", 14) + f"{'official':>10}{'observed':>10}{'unranked':>10}{'%':>7}"
    print("  " + head)
    print("  " + "-" * width(head))
    for path, official, observed in coverage(rows, SCALE_YEAR):
        gap = official - observed
        print("  " + pad(path, 14)
              + f"{official:>10,}{observed:>10,}{gap:>10,}{100 * gap / official:>6.1f}%")

    print("\nRun python3 -m pool.fit for the taker density each exam draws from.")


if __name__ == "__main__":
    main()
