"""Rank Taiwanese universities, departments and application groups by difficulty.

Covers both admission systems:
  - 一般大學 via 分發入學, 繁星推薦 and 個人申請
  - 科技大學 via 四技二專聯合登記分發 (統測), from tech-cutoffs.tsv

UAC cutoffs are converted to an equal-subject percentile from CEEC's marginal
score distributions. 術科 rows preserve their old within-year position as a
calibrated fallback. This refines comparisons between departments that select
different subjects.

The two systems use different exams sat by different populations, so their raw
normalised scores are not comparable. They are bridged by the 56 departments at
6 universities that admit through both systems: the same department awarding the
same degree, so no assumption about relative ability of the 高中 and 高職 pools
is needed. A least-squares fit over those matched departments maps 統測 scores
onto the 分發入學 axis. The two partially collected 學測 paths are then mapped
onto that fixed admitted-seat axis.

Scores average all available years (108-114) within each admission path, then
average paths by their annual admitted seats. This prevents a path with seven
years of source data from outweighing one with two years merely due to coverage.
Entities that have closed or merged are kept and marked `active=0`.
"""

import collections
import os

import ceec_score
import deptname
import gender
import tsvio

HERE = os.path.dirname(__file__)
LATEST = "114"
SOURCES = {"uac": "uac-cutoffs.tsv", "tech": "tech-cutoffs.tsv"}
# The 學測 routes into 一般大學, each its own exam field. `system` stays the kind
# of institution; `path` is how the seat was won.
EXTRA = {"star": "star-cutoffs.tsv", "apply": "apply-cutoffs.tsv"}


def identify_department(row):
    """Preserve the source 系組 name, then attach its reporting department."""
    row["application_group"] = row["dept"].strip()
    row["dept"] = deptname.normalize(row["application_group"])


def load(system, distributions=None):
    """Rows for one admission system.

    Department names are normalised, so the several 組 a department admits
    through arrive under one name.
    """
    for row in tsvio.read_rows(os.path.join(HERE, SOURCES[system])):
        row["system"] = system
        row["path"] = system
        identify_department(row)
        row["seats"] = int(row["seats"])
        row["norm"] = float(row["norm"])
        row["basis"] = row["norm"]
        if system == "uac" and distributions is not None:
            percentile = distributions.formula_percentile(
                row["year"], row["subjects"], row["cutoff"]
            )
            if percentile is not None:
                row["basis"] = percentile
                row["ceec_percentile"] = percentile
        yield row


def load_star():
    """繁星推薦 rows, ordered so that bigger is better.

    `gpa` is the marginal admittee's rank inside their own school, where 1%
    beats 17%, so it is negated to match every other path. 第八類學群 reports
    通過篩選 ahead of a 甄試 rather than admission, and is left out.
    """
    for row in tsvio.read_rows(os.path.join(HERE, EXTRA["star"])):
        admitted = int(row["admitted"] or 0)
        if row["group"] == "eight" or not row["gpa"] or not admitted:
            continue
        row["system"], row["path"] = "uac", "star"
        row["school"] = row["college"]
        identify_department(row)
        row["seats"] = admitted
        row["norm"] = -float(row["gpa"])
        row["basis"] = row["norm"]
        yield row


def load_apply():
    """個人申請 rows, dropping the ones OCR could not be trusted on.

    A `norm` above 1 is impossible and means a subject was lost from a composite
    label, and a blank 校系名稱 cannot be joined to a department.
    """
    for row in tsvio.read_rows(os.path.join(HERE, EXTRA["apply"])):
        if not row["norm"] or not row["dept"].strip():
            continue
        norm = float(row["norm"])
        admitted = int(row["admitted"] or 0)
        if norm > 1 or not admitted:
            continue
        row["system"], row["path"] = "uac", "apply"
        row["school"] = row["college"]
        identify_department(row)
        row["seats"] = admitted
        row["norm"] = norm
        row["basis"] = row["norm"]
        yield row


def joinable(rows, known):
    """Keep only rows whose department also admits through 分發入學 that year.

    OCR and abbreviation leave names that match nothing, and letting those
    through would invent departments in the department ranking.
    """
    return [r for r in rows if (r["year"], r["school"], r["dept"]) in known]


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


def curve(rows, source, target, key):
    """Set `target` to where `source` falls among the seats it competes with, 0-100.

    Keying on year and admission path curves each route against its own field,
    which makes the bridge fit on comparable scales. Keying on year alone
    curves the merged pool once both systems are on one axis. Rows sharing a
    value share the midpoint of the seats they span.
    """
    groups = collections.defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    for group in groups.values():
        values, percentiles = ceec_score.weighted_midpoints(group, source)
        percentile_of = dict(zip(values, percentiles))
        for row in group:
            row[target] = 100.0 * percentile_of[row[source]]


def by_dept(rows, field="pct"):
    """Collapse rows to (`field`, seats) per (year, school, department)."""
    groups = collections.defaultdict(list)
    for row in rows:
        groups[(row["year"], row["school"], row["dept"])].append(row)
    out = {}
    for key, group in groups.items():
        seats = sum(row["seats"] for row in group)
        if seats:
            out[key] = (wmean(group, field), seats)
    return out


def fit_bridge(reference, path):
    """Least-squares map one path onto a reference path over matched departments.

    Each mapping holds (score, seats) by (year, school, department). The fit is
    weighted by the smaller of the two intakes, which is what limits how
    precisely a match locates the line.
    """
    keys = sorted(set(reference) & set(path))
    xs = [path[k][0] for k in keys]
    ys = [reference[k][0] for k in keys]
    ws = [min(reference[k][1], path[k][1]) for k in keys]
    total_w = sum(ws)
    mean_x = sum(w * x for w, x in zip(ws, xs)) / total_w
    mean_y = sum(w * y for w, y in zip(ws, ys)) / total_w
    slope = sum(w * (x - mean_x) * (y - mean_y) for w, x, y in zip(ws, xs, ys)) / sum(
        w * (x - mean_x) ** 2 for w, x in zip(ws, xs)
    )
    intercept = mean_y - slope * mean_x
    variance = sum(w * (y - mean_y) ** 2 for w, y in zip(ws, ys))
    residual = sum(
        w * (y - (intercept + slope * x)) ** 2 for w, x, y in zip(ws, xs, ys)
    )
    stats = {
        "n": len(keys),
        "depts": len({(k[1], k[2]) for k in keys}),
        "schools": len({k[1] for k in keys}),
        "r2": 1 - residual / variance,
        "lo": min(xs),
        "hi": max(xs),
    }
    return intercept, slope, stats


def aggregate(rows, key):
    """Average within admission path, then average paths by annual seats.

    Source coverage differs by path: 分發入學 has seven years while the
    current 繁星 and 個申 samples have two. Within a path, rows and years are
    weighted by admitted seats. Across paths, the weight is average annual seats,
    so the number of downloaded years is not itself a vote in the final score.
    """
    groups = collections.defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    out = []
    for name, group in groups.items():
        path_groups = collections.defaultdict(list)
        for row in group:
            path_groups[row["path"]].append(row)
        paths = []
        for path_group in path_groups.values():
            path_years = len({r["year"] for r in path_group})
            path_seats = sum(r["seats"] for r in path_group)
            if path_years and path_seats:
                paths.append(
                    {
                        "score": wmean(path_group, "score"),
                        "seats": path_seats / path_years,
                    }
                )
        seats_avg = sum(path["seats"] for path in paths)
        if not seats_avg:
            continue
        last_year = max(r["year"] for r in group)
        years = len({r["year"] for r in group})
        systems = {r["system"] for r in group}
        out.append(
            {
                "key": name,
                "score": wmean(paths, "score"),
                "years": years,
                "last_year": last_year,
                "active": int(last_year == LATEST),
                "seats_avg": seats_avg,
                "system": "both" if len(systems) > 1 else systems.pop(),
            }
        )
    return sorted(out, key=lambda d: -d["score"])


def write(path, header, ranked, counts):
    """Write a ranking with blank English-name slots and optional gender counts.

    `counts` maps a row key to (men, women); absent keys leave those cells blank.
    """
    matched = 0
    with open(path, "w", encoding="utf-8") as f:
        f.write("\t".join(header) + "\n")
        for i, d in enumerate(ranked, 1):
            fields = [str(i)]
            names = d["key"] if isinstance(d["key"], tuple) else (d["key"],)
            for name in names:
                fields += [name, ""]
            fields += [f"{d['score']:.2f}", str(d["years"]), str(d["last_year"])]
            fields += [str(d["active"]), f"{d['seats_avg']:.1f}", d["system"]]
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
    distributions = ceec_score.ScoreDistributions.load(
        os.path.join(HERE, "ceec-scores.tsv")
    )
    uac_rows = list(load("uac", distributions))
    tech_rows = list(load("tech"))
    adjusted = sum("ceec_percentile" in row for row in uac_rows)
    fallbacks = ceec_score.calibrate_fallbacks(uac_rows)
    print(
        f"CEEC: adjusted {adjusted} of {len(uac_rows)} UAC rows;"
        f" calibrated {fallbacks} 術科 fallbacks"
    )
    unify_spelling(uac_rows + tech_rows)
    known = {(r["year"], r["school"], r["dept"]) for r in uac_rows}
    extra = {}
    for path, loader in (("star", load_star), ("apply", load_apply)):
        got = list(loader())
        kept = joinable(got, known)
        extra[path] = kept
        print(f"{path}: {len(kept)} of {len(got)} rows join a 分發入學 department")

    rows = uac_rows + tech_rows + extra["star"] + extra["apply"]
    unify_spelling(rows)
    # Keep the validated 統測 bridge on the old fraction-of-maximum ordering.
    # CEEC improves repeatability inside UAC, but using it as the bridge target
    # raises leave-one-school-out error from 11.60 to 12.63 points.
    curve(rows, "norm", "bridge_pct", lambda r: (r["year"], r["path"]))
    curve(rows, "basis", "pct", lambda r: (r["year"], r["path"]))

    for row in uac_rows:
        row["merged"] = row["pct"]
    # 統測 is a different population, so retain its independently validated
    # fraction-of-maximum bridge while refining UAC rows on the merged side.
    intercept, slope, stats = fit_bridge(
        by_dept(uac_rows, "bridge_pct"), by_dept(tech_rows, "bridge_pct")
    )
    print(
        f"bridge: uac = {intercept:.3f} + {slope:.4f} * tech"
        f"   R2={stats['r2']:.3f}  n={stats['n']} dept-years"
        f"  ({stats['depts']} depts, {stats['schools']} schools,"
        f" tech {stats['lo']:.1f}-{stats['hi']:.1f})"
    )
    for row in tech_rows:
        row["merged"] = intercept + slope * row["pct"]

    # The established 分發+統測 cohort defines the published percentile. The
    # extra paths cover only eight schools in two years, so including their seats
    # in this curve would redefine every existing score because collection is
    # partial. Match each extra path directly onto the fixed score axis instead.
    curve(uac_rows + tech_rows, "merged", "score", lambda r: r["year"])
    uac_score = by_dept(uac_rows, "score")
    for path, path_rows in extra.items():
        intercept, slope, stats = fit_bridge(uac_score, by_dept(path_rows))
        print(
            f"bridge: score = {intercept:.3f} + {slope:.4f} * {path}"
            f"   R2={stats['r2']:.3f}  n={stats['n']} dept-years"
            f"  ({stats['depts']} depts, {stats['schools']} schools,"
            f" {path} {stats['lo']:.1f}-{stats['hi']:.1f})"
        )
        for row in path_rows:
            row["score"] = intercept + slope * row["pct"]
    tail = ["score", "years", "last_year", "active", "seats_avg", "system"]
    tail += ["men", "women", "pct_women"]
    by_dept_counts = gender.load()
    by_school_counts = gender.school_totals(by_dept_counts)
    write(
        os.path.join(HERE, "rank-universities.tsv"),
        ["rank", "school", "school_en"] + tail,
        aggregate(rows, lambda r: r["school"]),
        lambda school: by_school_counts.get(school),
    )
    write(
        os.path.join(HERE, "rank-departments.tsv"),
        ["rank", "school", "school_en", "dept", "dept_en"] + tail,
        aggregate(rows, lambda r: (r["school"], r["dept"])),
        lambda key: gender.lookup(by_dept_counts, *key),
    )
    write(
        os.path.join(HERE, "rank-application-groups.tsv"),
        [
            "rank",
            "school",
            "school_en",
            "dept",
            "dept_en",
            "application_group",
            "application_group_en",
        ]
        + tail,
        aggregate(
            uac_rows + tech_rows,
            lambda r: (r["school"], r["dept"], r["application_group"]),
        ),
        lambda key: None,
    )


if __name__ == "__main__":
    main()
