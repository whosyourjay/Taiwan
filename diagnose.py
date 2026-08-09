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

import ceec_score
import rank_uac

PATHS = ["uac", "tech", "star", "apply"]
DEPTS_PER_SCHOOL = 5

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
# 繁星 and 個人申請 were only collected for 110-111, so this is the latest year
# all four paths can be compared on the same curve.
SCALE_YEAR = "111"

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


def at(pairs, x):
    """Interpolate y at x, continuing along the end segments beyond the data."""
    return ceec_score.interpolate([p[0] for p in pairs], [p[1] for p in pairs],
                                  x, extrapolate=True)


def scale_endpoints(rows, year, field):
    """Where each path's own 0-100 curve lands on `field`, that year.

    `pct` is a path's position among the seats it competes with, so it spans
    0-100 by construction. What differs is how much of the national axis that
    span is mapped onto: a path bridged with a shallow slope is compressed into
    a narrow band, and cannot separate its departments however well it ranks
    them internally.
    """
    out = {}
    for path in PATHS:
        group = [r for r in rows if r["path"] == path and r["year"] == year]
        merged = collections.defaultdict(list)
        for row in group:
            merged[row["pct"]].append(row[field])
        pairs = sorted((p, sum(s) / len(s)) for p, s in merged.items())
        if len(pairs) >= 2:
            out[path] = (at(pairs, 0.0), at(pairs, 100.0))
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
    head += "".join(f"{p:>8}" for p in PATHS) + f"{'spread':>9}"
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
                line += f"{paths[path][0]:>8.1f}" if path in paths else f"{'-':>8}"
            scores = [v[0] for v in paths.values()]
            gap = max(scores) - min(scores)
            line += f"{gap:>9.1f}" if len(scores) > 1 else f"{'':>9}"
            print(line)

    print("\nScores are 0-100 over admitted seats nationally, so they are"
          " comparable across paths.")
    print("A blank spread means only one path was collected for that department.")
    print(f"{'/'.join(PINNED)} never show a 繁星 score: those are 第八類學群,"
          " which reports 通過篩選")
    print("ahead of a 甄試 rather than admission, so load_star() excludes them.")

    print(f"\nSeat coverage, year {SCALE_YEAR}")
    head = pad("path", 14) + f"{'official':>10}{'observed':>10}{'unranked':>10}{'%':>7}"
    print("  " + head)
    print("  " + "-" * width(head))
    for path, official, observed in coverage(rows, SCALE_YEAR):
        gap = official - observed
        print("  " + pad(path, 14)
              + f"{official:>10,}{observed:>10,}{gap:>10,}{100 * gap / official:>6.1f}%")

    # The shipped score counts unranked seats as a floor beneath every ranked
    # row. That is only defensible where the missing seats really are the weaker
    # ones, so show the ranked-only axis beside it.
    rank_uac.curve(rows, "rank_basis", "score_ranked", lambda r: r["year"])
    floored = scale_endpoints(rows, SCALE_YEAR, "score")
    ranked = scale_endpoints(rows, SCALE_YEAR, "score_ranked")

    print(f"\nExam scale -> final score, year {SCALE_YEAR}"
          " (the latest all four paths cover)")
    print("  " + pad("exam", 20) + pad("path", 8)
          + f"{'ranked seats only':>22}{'unranked as floor':>22}")
    head = pad("", 28) + f"{'0 ->':>11}{'100 ->':>11}{'0 ->':>11}{'100 ->':>11}"
    print("  " + head)
    print("  " + "-" * width(head))
    for path in PATHS:
        if path not in ranked:
            continue
        lo, hi = ranked[path]
        flo, fhi = floored[path]
        print("  " + pad(EXAMS[path], 20) + pad(path, 8)
              + f"{lo:>11.1f}{hi:>11.1f}{flo:>11.1f}{fhi:>11.1f}")
    print("  Placing every unranked seat below every ranked one lifts the whole"
          " axis off 0.")
    print("  It only holds where the uncollected seats are genuinely the weaker"
          " ones, which")
    print("  is false for 個人申請: 8 elite schools are collected and the rest"
          " of the country")
    print("  is not.")


if __name__ == "__main__":
    main()
