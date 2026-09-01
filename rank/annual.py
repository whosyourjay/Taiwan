"""Complete the ranking as an annual department-by-route panel.

Observed cutoffs supply both seats and ability. The ministry's 表7-2 supplies
115 route quotas even where no cutoff is readable. Gaps inside an active
department are interpolated between its own route-years, or carried from its
nearest year; ability then falls back through the department, school, route and
national levels. Every estimate keeps its method in the output.
"""

import collections
import os

from lib import deptname, schoolname, tsvio
from lib.paths import data_path, ranking_path


QUOTA_PATHS = ("uac", "star", "apply", "tech")
QUOTAS = "university-quotas.tsv"
UAC_SEATS = "uac-seats.tsv"
OUTPUT = "rank-history.tsv"
TOTALS = "admission-totals.tsv"
COMPLETE_YEARS = {
    "uac": set(range(107, 116)),
    "tech": set(range(107, 116)),
    "star": set(range(108, 115)),
    "star_eight": set(range(108, 115)),
    "apply": {110},
}


def school_key(name):
    """Current institution name, with ministry campus suffixes removed."""
    return schoolname.without_campus(schoolname.current(name))


def entity_of(row):
    return school_key(row["school"]), deptname.key(row["dept"])


def weighted(group, field):
    live = [(float(row[field]), float(row["seats"])) for row in group
            if row.get(field) not in (None, "") and float(row["seats"]) > 0]
    total = sum(seats for _, seats in live)
    return sum(value * seats for value, seats in live) / total if total else None


def seat_evidence():
    """Every named seat, including rows whose cutoff cannot be scored."""
    out = []
    for filename, route in (("uac-cutoffs.tsv", "uac"),
                            ("tech-cutoffs.tsv", "tech")):
        for row in tsvio.read_rows(data_path(filename)):
            out.append({
                "year": row["year"], "school": row["school"],
                "dept": row["dept"], "path": route,
                "seats": float(row["seats"] or 0),
            })
    for row in tsvio.read_rows(data_path("star-cutoffs.tsv")):
        route = "star_eight" if row["group"] == "eight" else "star"
        seats = row["quota"] if route == "star_eight" else row["admitted"]
        out.append({
            "year": row["year"], "school": row["college"],
            "dept": row["dept"], "path": route, "seats": float(seats or 0),
        })
    for row in tsvio.read_rows(data_path("apply-cutoffs.tsv")):
        out.append({
            "year": row["year"], "school": row["college"],
            "dept": row["dept"], "path": "apply",
            "seats": float(row["admitted"] or row["seats"] or 0),
        })
    return [row for row in out if row["school"] and row["dept"].strip()
            and row["seats"] > 0]


def observed_cells(rows, seat_rows):
    """Join all seats to the subset carrying annual ability evidence."""
    ability_groups = collections.defaultdict(list)
    for row in rows:
        key = (*entity_of(row), int(row["year"]), row["path"])
        ability_groups[key].append(row)
    seat_groups = collections.defaultdict(list)
    for row in seat_rows:
        key = (*entity_of(row), int(row["year"]), row["path"])
        seat_groups[key].append(row)
    cells, labels = {}, collections.defaultdict(list)
    year_names, covered = collections.defaultdict(set), set()
    for row in seat_rows:
        covered.add((int(row["year"]), school_key(row["school"]), row["path"]))
    for school, dept_key, year, route in ability_groups.keys() | seat_groups.keys():
        entity = school, dept_key
        scored = ability_groups[(school, dept_key, year, route)]
        seated = seat_groups[(school, dept_key, year, route)] or scored
        seats = sum(float(row["seats"]) for row in seated)
        ability = weighted(scored, "score")
        cells[(entity, year, route)] = {
            "entity": entity, "year": year, "route": route,
            "seats": seats, "ability": ability,
            "seats_method": "observed",
            "ability_method": "observed" if ability is not None else "",
            "input_rows": len(seated),
        }
        for row in seated + scored:
            labels[entity].append(
                (year, float(row["seats"]), deptname.normalize(row["dept"]))
            )
            year_names[(entity, year)].add(row["school"])
    return cells, labels, year_names, covered


def quota_rows(path=None):
    source = path or data_path(QUOTAS)
    return list(tsvio.read_rows(source)) if os.path.exists(source) else []


def uac_seat_rows(path=None):
    source = path or data_path(UAC_SEATS)
    return list(tsvio.read_rows(source)) if os.path.exists(source) else []


def admission_totals(path=None):
    source = path or data_path(TOTALS)
    return list(tsvio.read_rows(source)) if os.path.exists(source) else []


def quota_route(route, history, latest=None):
    """Put medical-only 繁星 quotas back under the eighth-category route."""
    if route == "star" and "star_eight" in history:
        latest = latest or {}
        if latest.get("star_eight", -1) > latest.get("star", -1):
            return "star_eight"
    return route


def add_quotas(cells, labels, year_names, quotas):
    """Use official quota seats, including zero where a known route closed."""
    routes = collections.defaultdict(set)
    latest = collections.defaultdict(dict)
    for entity, _, route in cells:
        routes[entity].add(route)
    for (entity, year, route), cell in cells.items():
        if float(cell.get("seats") or 0) > 0:
            latest[entity][route] = max(year, latest[entity].get(route, year))
    totals = collections.Counter()
    for row in quotas:
        entity, year = entity_of(row), int(row["year"])
        for route in QUOTA_PATHS:
            totals[(entity, year, route)] += float(row.get(route) or 0)
        labels[entity].append(
            (year, float(row.get("total") or 0), deptname.normalize(row["dept"]))
        )
        year_names[(entity, year)].add(row["school"])
    for (entity, year, source_route), seats in totals.items():
        route = quota_route(source_route, routes[entity], latest[entity])
        if not seats and route not in routes[entity]:
            continue
        key = entity, year, route
        cell = cells.setdefault(key, {
            "entity": entity, "year": year, "route": route,
            "ability": None, "ability_method": "", "input_rows": 0,
        })
        cell["seats"], cell["seats_method"] = seats, "moe_quota"
        routes[entity].add(route)
        if source_route == "star":
            other = "star_eight" if route == "star" else "star"
            if other in routes[entity]:
                other_cell = cells.setdefault((entity, year, other), {
                    "entity": entity, "year": year, "route": other,
                    "ability": None, "ability_method": "", "input_rows": 0,
                })
                other_cell["seats"], other_cell["seats_method"] = 0.0, "moe_quota"


def deduct_returns(cells, entity, year, returned):
    """Estimate which earlier-route quotas became final UAC seats."""
    for route in ("apply", "star", "star_eight", "tech"):
        cell = cells.get((entity, year, route))
        available = float(cell.get("seats") or 0) if cell else 0.0
        moved = min(returned, available)
        if moved:
            cell["seats"] = available - moved
            cell["seats_method"] += "-uac_return_estimate"
            returned -= moved
        if returned <= 0:
            break


def add_uac_seats(cells, labels, year_names, rows):
    """Use capacity only where a completed year's actual admissions are absent."""
    totals, counts = collections.Counter(), collections.Counter()
    for row in rows:
        entity, year = entity_of(row), int(row["year"])
        totals[(entity, year)] += float(row.get("seats") or 0)
        counts[(entity, year)] += 1
        labels[entity].append(
            (year, float(row.get("seats") or 0), deptname.normalize(row["dept"]))
        )
        year_names[(entity, year)].add(row["school"])
    actual_years = {year for (_, year, route), cell in cells.items()
                    if route == "uac" and cell["seats_method"] == "observed"}
    years = {year for _, year in totals} - actual_years
    for (entity, year, route), cell in cells.items():
        if route == "uac" and year in years and (entity, year) not in totals:
            cell["seats"], cell["seats_method"] = 0.0, "uac_post_return"
    for (entity, year), seats in totals.items():
        if year not in years:
            continue
        key = entity, year, "uac"
        cell = cells.setdefault(key, {
            "entity": entity, "year": year, "route": "uac",
            "ability": None, "ability_method": "", "input_rows": 0,
        })
        initial = float(cell.get("seats") or 0)
        if seats > initial:
            deduct_returns(cells, entity, year, seats - initial)
        cell["seats"], cell["seats_method"] = seats, "uac_post_return"
        cell["input_rows"] = counts[(entity, year)]


def source_complete(entity, year, route, covered):
    return year in COMPLETE_YEARS.get(route, ()) or (year, entity[0], route) in covered


def expand(cells, covered):
    """Create every active year-route cell between an entity's endpoints."""
    years, routes = collections.defaultdict(set), collections.defaultdict(set)
    for entity, year, route in cells:
        years[entity].add(year)
        routes[entity].add(route)
    for entity, seen in years.items():
        for year in range(min(seen), max(seen) + 1):
            for route in routes[entity]:
                key = entity, year, route
                if key in cells:
                    continue
                complete = source_complete(entity, year, route, covered)
                cells[key] = {
                    "entity": entity, "year": year, "route": route,
                    "seats": 0.0 if complete else None, "ability": None,
                    "seats_method": "structural_zero" if complete else "",
                    "ability_method": "", "input_rows": 0,
                }


def estimate(series, year):
    """Exact value, a linear span, or the nearest reporting year."""
    if year in series:
        return series[year], str(year)
    below = [found for found in series if found < year]
    above = [found for found in series if found > year]
    if below and above:
        left, right = max(below), min(above)
        share = (year - left) / (right - left)
        return series[left] + share * (series[right] - series[left]), f"{left},{right}"
    nearest = min(series, key=lambda found: (abs(found - year), found))
    return series[nearest], str(nearest)


def fill_series(cells, field):
    """Fill one value from the same department-route across years."""
    series = collections.defaultdict(dict)
    for (entity, year, route), cell in cells.items():
        if cell.get(field) is not None:
            series[(entity, route)][year] = float(cell[field])
    method = f"{field}_method"
    for (entity, year, route), cell in cells.items():
        if cell.get(field) is not None or not series[(entity, route)]:
            continue
        value, sources = estimate(series[(entity, route)], year)
        cell[field] = value
        cell[method] = ("interpolated:" if "," in sources else "nearest:") + sources


def reference_means(cells, key):
    moments, weights = collections.defaultdict(float), collections.defaultdict(float)
    for cell in cells.values():
        seats = float(cell.get("seats") or 0)
        if cell.get("ability") is None or seats <= 0:
            continue
        group = key(cell)
        moments[group] += float(cell["ability"]) * seats
        weights[group] += seats
    return {group: moments[group] / weight for group, weight in weights.items()}


def fill_ability_fallbacks(cells):
    """Fill routes with no own history from the narrowest available peer."""
    keys = (
        ("department_year", lambda c: (c["entity"], c["year"])),
        ("department", lambda c: c["entity"]),
        ("school_route_year", lambda c: (c["entity"][0], c["route"], c["year"])),
        ("school_year", lambda c: (c["entity"][0], c["year"])),
        ("school_route", lambda c: (c["entity"][0], c["route"])),
        ("school", lambda c: c["entity"][0]),
        ("route_year", lambda c: (c["route"], c["year"])),
        ("year", lambda c: c["year"]),
        ("national", lambda c: "all"),
    )
    references = [(name, key, reference_means(cells, key)) for name, key in keys]
    for cell in cells.values():
        if cell.get("ability") is not None:
            continue
        for name, key, means in references:
            if key(cell) in means:
                cell["ability"] = means[key(cell)]
                cell["ability_method"] = name
                break


def total_route(route):
    return "star" if route in ("star", "star_eight") else route


def calibrate_totals(cells, totals):
    """Make every published national seat count, recording the expansion."""
    targets = {(int(row["year"]), row["path"]): float(row["admitted"])
               for row in totals}
    for (year, route), target in targets.items():
        group = [cell for cell in cells.values()
                 if cell["year"] == year and total_route(cell["route"]) == route]
        base = sum(float(cell["seats"] or 0) for cell in group)
        if not base or route == "tech_select":
            continue
        imputed = [cell for cell in group
                   if cell["seats_method"].startswith(("interpolated", "nearest"))]
        estimated = sum(float(cell["seats"] or 0) for cell in imputed)
        if not estimated or target < base - estimated:
            continue
        scale = (target - base + estimated) / estimated
        for cell in imputed:
            cell["seats"] = float(cell["seats"] or 0) * scale
            cell["seat_scale"] = scale
            if abs(scale - 1.0) > 1e-9 and cell["seats_method"] != "structural_zero":
                cell["seats_method"] += "+national_scale"


def display_names(labels):
    """Prefer the latest reported department spelling."""
    return {entity: max(found, key=lambda item: (item[0], item[1]))[2]
            for entity, found in labels.items()}


def historical_name(year_names, entity, year):
    exact = year_names.get((entity, year))
    if exact:
        return " | ".join(sorted(exact))
    available = {found for found_entity, found in year_names if found_entity == entity}
    nearest = min(available, key=lambda found: (abs(found - year), found))
    return " | ".join(sorted(year_names[(entity, nearest)]))


def output_rows(cells, labels, year_names):
    names = display_names(labels)
    out = []
    for (entity, year, route), cell in sorted(
            cells.items(), key=lambda item: (item[0][1], item[0][0], item[0][2])):
        school, _ = entity
        out.append({
            "year": year, "school": school,
            "school_year_name": historical_name(year_names, entity, year),
            "dept": names[entity], "route": route,
            "seats": round(float(cell["seats"]), 2),
            "ability": round(float(cell["ability"]), 3),
            "seats_method": cell["seats_method"],
            "seat_scale": round(float(cell.get("seat_scale", 1.0)), 6),
            "ability_method": cell["ability_method"],
            "input_rows": cell["input_rows"],
        })
    return out


def build(rows, quotas=None, seat_rows=None, totals=None, uac_seats=None):
    seats = seat_evidence() if seat_rows is None else seat_rows
    cells, labels, year_names, covered = observed_cells(rows, seats)
    add_quotas(cells, labels, year_names, quota_rows() if quotas is None else quotas)
    add_uac_seats(cells, labels, year_names,
                  uac_seat_rows() if uac_seats is None else uac_seats)
    expand(cells, covered)
    fill_series(cells, "seats")
    fill_series(cells, "ability")
    fill_ability_fallbacks(cells)
    calibrate_totals(cells, admission_totals() if totals is None else totals)
    return output_rows(cells, labels, year_names)


def aggregate(rows, columns):
    """Rank entities from every estimated annual seat, not readable bars alone."""
    groups = collections.defaultdict(list)
    for row in rows:
        key = tuple(row[column] for column in columns)
        groups[key].append(row)
    out = []
    for key, group in groups.items():
        live = [row for row in group if float(row["seats"]) > 0]
        years = {row["year"] for row in group}
        score = weighted(live, "ability")
        if score is None or not years:
            continue
        by_path = {}
        for route in sorted({row["route"] for row in live}):
            value = weighted([row for row in live if row["route"] == route], "ability")
            if value is not None:
                by_path[route] = value
        out.append({
            "key": key[0] if len(key) == 1 else key, "score": score,
            "years": len(years), "last_year": max(years),
            "seats_avg": sum(float(row["seats"]) for row in live) / len(years),
            "by_path": by_path,
        })
    return sorted(out, key=lambda row: -row["score"])


def write(rows, target=None):
    target = target or ranking_path(OUTPUT)
    written = tsvio.write_rows(target, rows)
    print(f"{written:>5} rows -> {os.path.basename(target)}")
    return written


def main():
    from rank import uac

    write(build(uac.build_rows()))


if __name__ == "__main__":
    main()
