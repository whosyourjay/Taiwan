"""Rank Taiwanese universities and departments by undergraduate admission difficulty.

Covers both admission systems:
  - 一般大學 via 分發入學 (學測 + 分科測驗), from uac-cutoffs.tsv
  - 科技大學 via 四技二專聯合登記分發 (統測), from tech-cutoffs.tsv

Each cutoff is normalised to a fraction of its own maximum weighted score, which
makes departments with different subject weightings comparable inside a system.

The two systems use different exams sat by different populations, so their raw
normalised scores are not comparable. They are bridged by the 46 departments at
5 universities that admit through both systems: the same department awarding the
same degree, so no assumption about relative ability of the 高中 and 高職 pools
is needed. A least-squares fit over those matched departments maps 統測 scores
onto the 分發入學 axis, and `score` reports every institution on that axis.

Scores average all available years (108-114), weighted by admitted seats.
Entities that have closed or merged are kept and marked `active=0`.
"""

import collections
import os

import gender
import deptname

HERE = os.path.dirname(__file__)
LATEST = "114"
SOURCES = {"uac": "uac-cutoffs.tsv", "tech": "tech-cutoffs.tsv"}


def load(system):
    """Rows for one admission system, dropping 術科 系組 whose scale differs.

    Department names are normalised, so the several 組 a department admits
    through arrive under one name.
    """
    with open(os.path.join(HERE, SOURCES[system]), encoding="utf-8") as f:
        cols = f.readline().rstrip("\n").split("\t")
        for line in f:
            row = dict(zip(cols, line.rstrip("\n").split("\t")))
            if "術" in row.get("subjects", ""):
                continue
            row["system"] = system
            row["dept"] = deptname.normalize(row["dept"])
            row["seats"] = int(row["seats"])
            row["norm"] = float(row["norm"])
            yield row


def unify_spelling(rows):
    """Give each department one name, the spelling that admitted the most students."""
    seats = collections.defaultdict(collections.Counter)
    for row in rows:
        seats[(row["school"], deptname.key(row["dept"]))][row["dept"]] += row["seats"]
    names = {k: c.most_common(1)[0][0] for k, c in seats.items()}
    for row in rows:
        row["dept"] = names[(row["school"], deptname.key(row["dept"]))]


def wmean(rows, field):
    seats = sum(r["seats"] for r in rows)
    return sum(r[field] * r["seats"] for r in rows) / seats if seats else 0.0


def level_years(rows):
    """Set `adj`: `norm` with the year's own difficulty removed.

    An exam that ran easy lifts every cutoff that year, so pooling years raw
    rewards whoever happens to be present in the generous ones. The shift is
    measured on departments admitting in every year, so a changing mix of
    departments cannot masquerade as a change in difficulty.
    """
    seen = collections.defaultdict(set)
    for row in rows:
        seen[(row["school"], row["dept"])].add(row["year"])
    years = {r["year"] for r in rows}
    panel = [r for r in rows if len(seen[(r["school"], r["dept"])]) == len(years)]
    grand = wmean(panel, "norm")
    effect = {y: wmean([r for r in panel if r["year"] == y], "norm") - grand for y in years}
    for row in rows:
        row["adj"] = row["norm"] - effect[row["year"]]
    return effect


def by_dept(rows):
    """Collapse a system's rows to (score, seats) per (year, school, dept)."""
    groups = collections.defaultdict(list)
    for row in rows:
        groups[(row["year"], row["school"], row["dept"])].append(row)
    return {
        key: (wmean(group, "adj"), sum(r["seats"] for r in group))
        for key, group in groups.items()
        if sum(r["seats"] for r in group)
    }


def fit_bridge(uac, tech):
    """Least-squares map from 統測 onto the 分發入學 axis, over dual-intake departments.

    Weighted by the smaller of a department-year's two intakes, which is what
    limits how precisely it locates the line. Giving a department one point per
    year it ran rather than one overall wins on leave-one-school-out error, and
    matches a dept-level random intercept tuned the same way.
    """
    keys = sorted(set(uac) & set(tech))
    xs = [tech[k][0] for k in keys]
    ys = [uac[k][0] for k in keys]
    ws = [min(uac[k][1], tech[k][1]) for k in keys]
    total_w = sum(ws)
    mean_x = sum(w * x for w, x in zip(ws, xs)) / total_w
    mean_y = sum(w * y for w, y in zip(ws, ys)) / total_w
    slope = sum(w * (x - mean_x) * (y - mean_y) for w, x, y in zip(ws, xs, ys)) / sum(
        w * (x - mean_x) ** 2 for w, x in zip(ws, xs)
    )
    intercept = mean_y - slope * mean_x
    total = sum(w * (y - mean_y) ** 2 for w, y in zip(ws, ys))
    resid = sum(w * (y - (intercept + slope * x)) ** 2 for w, x, y in zip(ws, xs, ys))
    stats = {
        "n": len(keys),
        "depts": len({(k[1], k[2]) for k in keys}),
        "schools": len({k[1] for k in keys}),
        "r2": 1 - resid / total,
        "lo": min(xs),
        "hi": max(xs),
    }
    return intercept, slope, stats


def aggregate(rows, key):
    """Seat-weighted mean across all years, grouped by `key`."""
    groups = collections.defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    out = []
    for name, group in groups.items():
        seats = sum(r["seats"] for r in group)
        if not seats:
            continue
        last_year = max(r["year"] for r in group)
        final = [r for r in group if r["year"] == last_year]
        final_seats = sum(r["seats"] for r in final)
        systems = {r["system"] for r in group}
        out.append(
            {
                "key": name,
                "score": wmean(group, "score"),
                "score_final": wmean(final, "score"),
                "raw": wmean(group, "norm"),
                "years": len({r["year"] for r in group}),
                "last_year": last_year,
                "active": int(last_year == LATEST),
                "seats_final": final_seats,
                "system": "both" if len(systems) > 1 else systems.pop(),
            }
        )
    return sorted(out, key=lambda d: -d["score"])


def write(path, header, ranked, key_fields, counts):
    """`counts` maps a row key to (men, women); absent keys leave the cells blank."""
    matched = 0
    with open(path, "w", encoding="utf-8") as f:
        f.write("\t".join(header) + "\n")
        for i, d in enumerate(ranked, 1):
            fields = [str(i)]
            fields += list(d["key"]) if key_fields > 1 else [d["key"]]
            fields += [f"{d['score']:.4f}", f"{d['score_final']:.4f}", f"{d['raw']:.4f}"]
            fields += [str(d["years"]), str(d["last_year"])]
            fields += [str(d["active"]), str(d["seats_final"]), d["system"]]
            found = counts(d["key"])
            if found and sum(found):
                men, women = found
                fields += [str(men), str(women), f"{women / (men + women):.3f}"]
                matched += 1
            else:
                fields += ["", "", ""]
            f.write("\t".join(fields) + "\n")
    print(f"{len(ranked):>5} rows -> {os.path.basename(path)}  ({matched} with gender)")


def main():
    uac_rows, tech_rows = list(load("uac")), list(load("tech"))
    unify_spelling(uac_rows + tech_rows)
    for system_rows in (uac_rows, tech_rows):
        level_years(system_rows)
    intercept, slope, stats = fit_bridge(by_dept(uac_rows), by_dept(tech_rows))
    print(
        f"bridge: uac = {intercept:.4f} + {slope:.4f} * tech"
        f"   R2={stats['r2']:.3f}  n={stats['n']} dept-years"
        f"  ({stats['depts']} depts, {stats['schools']} schools,"
        f" 統測 {stats['lo']:.2f}-{stats['hi']:.2f})"
    )
    for row in uac_rows:
        row["score"] = row["adj"]
    for row in tech_rows:
        row["score"] = intercept + slope * row["adj"]
    rows = uac_rows + tech_rows
    tail = ["score", "score_final", "score_raw", "years", "last_year", "active"]
    tail += ["seats_final", "system", "men", "women", "pct_women"]
    by_dept_counts = gender.load()
    by_school_counts = gender.school_totals(by_dept_counts)
    write(
        os.path.join(HERE, "rank-universities.tsv"),
        ["rank", "school"] + tail,
        aggregate(rows, lambda r: r["school"]),
        1,
        lambda school: by_school_counts.get(school),
    )
    write(
        os.path.join(HERE, "rank-departments.tsv"),
        ["rank", "school", "dept"] + tail,
        aggregate(rows, lambda r: (r["school"], r["dept"])),
        2,
        lambda key: gender.lookup(by_dept_counts, *key),
    )


if __name__ == "__main__":
    main()
