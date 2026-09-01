#!/usr/bin/env python3
"""Build the self-contained dark HTML report from current generated tables."""

import collections
import csv
import json
import os
from pathlib import Path

# Report generation rebuilds the representative 110 exam curves. Keep native libraries from
# turning that one local operation into a many-core job.
for variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                 "VECLIB_MAXIMUM_THREADS"):
    os.environ[variable] = "1"

ROOT = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
OUTPUT = ROOT / "rankings" / "ability-report.html"
EXAMS = {
    "gsat": {"label": "學測", "english": "GSAT", "colour": "#58a6ff"},
    "star": {"label": "繁星校排", "english": "Star rank", "colour": "#a78bfa"},
    "star_eight": {"label": "繁星八類", "english": "Star VIII", "colour": "#d8b4fe"},
    "tongce_a": {"label": "統測 A", "english": "TVE A", "colour": "#3fb950"},
    "tongce_b": {"label": "統測 B", "english": "TVE B", "colour": "#78d97b"},
    "tongce_c": {"label": "統測 C", "english": "TVE C", "colour": "#1f7a3f"},
    "zhikao": {"label": "指考／分科", "english": "AST", "colour": "#f85149"},
}
PATHS = {
    "uac": ("一般大學 分發入學", "uac-cutoffs.tsv", "seats"),
    "tech": ("四技登記分發", "tech-cutoffs.tsv", "seats"),
    "star": ("繁星推薦", "star-cutoffs.tsv", "admitted"),
    "apply": ("個人申請", "apply-cutoffs.tsv", "seats"),
    "tech_apply": ("四技甄選", "tech-apply-cutoffs.tsv", "seats"),
}


def rows(path):
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def number(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def readings(row):
    return {exam: number(row.get(exam)) for exam in EXAMS if row.get(exam)}


def departments():
    out = []
    for row in rows(ROOT / "rankings" / "ability-departments.tsv"):
        exams = readings(row)
        system = "tech" if any(name.startswith("tongce") for name in exams) else "general"
        out.append({
            "school": row["school"], "school_en": row["school_en"],
            "department": row["dept"], "department_en": row["dept_en"],
            "ability": number(row["ability"]), "seats": number(row["seats"]),
            "spread": number(row["spread"], 0), "system": system,
            "exams": exams,
        })
    return out


def universities():
    out = []
    for row in rows(ROOT / "rankings" / "ability-universities.tsv"):
        out.append({
            "rank": int(row["rank"]), "school": row["school"],
            "school_en": row["school_en"], "former": row["former_schools"],
            "ability": number(row["ability"]), "seats": number(row["seats"]),
            "spread": number(row["spread"], 0), "years": int(row["years"]),
            "pool_seats": number(row["pool_seats"]),
            "pool_ratio": number(row["ability_pool_ratio"]),
            "exams": readings(row),
        })
    return out


def coverage():
    counted = collections.defaultdict(lambda: [0, 0.0])
    for path, (_, filename, field) in PATHS.items():
        for row in rows(ROOT / "data" / filename):
            counted[(path, row["year"])][0] += 1
            counted[(path, row["year"])][1] += number(row.get(field), 0)
    published = {(row["path"], row["year"]): number(row["admitted"])
                 for row in rows(ROOT / "data" / "admission-totals.tsv")}
    out = []
    for (path, year), (bars, seats) in sorted(counted.items()):
        total_path = "tech_select" if path == "tech_apply" else path
        total = published.get((total_path, year))
        out.append({"path": path, "label": PATHS[path][0], "year": year,
                    "bars": bars, "seats": seats, "total": total,
                    "share": seats / total if total else None})
    return out


def destinations(university_rows):
    abilities = {row["school"]: row["ability"] for row in university_rows}
    out = []
    for row in rows(ROOT / "data" / "high-school-destinations.tsv"):
        out.append({"name": row["destination"], "type": row["destination_type"],
                    "students": int(row["students"]),
                    "ability": abilities.get(row["destination"]),
                    "graduates": int(row["graduates"])})
    return out


def entry_floor():
    found = [row for row in rows(ROOT / "data" / "high-school-ability.tsv")
             if row["year"] == "107" and "北一女" in row["school"]]
    return {"year": 107, "top_share": number(found[0]["pct_above"]),
            "cutoff_z": number(found[0]["cutoff_z"])} if found else None


def curves():
    """Representative 110 exam curves for the cross-exam figure."""
    import numpy as np

    from pool import ability

    _, splines = ability.curves("110")
    out = []
    for exam, spline in sorted(splines.items()):
        points = []
        for step in range(201):
            bottom = step / 200
            level = max(0.0, min(1.0, float(spline(bottom))))
            points.append([100 * bottom, 100 * level])
        sample = np.clip(spline(np.linspace(0.0, 1.0, 20_001)), 0.0, 1.0)
        counts, _ = np.histogram(sample, bins=100, range=(0.0, 1.0))
        kernel = np.array([1, 2, 3, 2, 1], dtype=float) / 9
        density = np.convolve(counts, kernel, mode="same") / (len(sample) / 100)
        out.append({"exam": exam, "points": points,
                    "density": [[index + 0.5, float(value)]
                                for index, value in enumerate(density)]})
    return out


def page_data(include_curves=True):
    university_rows, department_rows = universities(), departments()
    destination_rows = destinations(university_rows)
    assessment = rows(ROOT / "assessment-pool.tsv")
    return {
        "exams": EXAMS, "universities": university_rows,
        "departments": department_rows, "coverage": coverage(),
        "destinations": destination_rows, "entry_floor": entry_floor(),
        "curves": curves() if include_curves else [],
        "metrics": {
            "universities": len(university_rows), "departments": len(department_rows),
            "seats": sum(row["seats"] for row in department_rows),
            "assessment_pool": number(assessment[0]["B"]) if assessment else None,
            "destination_students": sum(row["students"] for row in destination_rows),
        },
    }


def render(data, output=OUTPUT):
    page = (HERE / "report.html").read_text(encoding="utf-8")
    for marker, filename in (("__CSS__", "report.css"), ("__JS__", "report.js")):
        page = page.replace(marker, (HERE / filename).read_text(encoding="utf-8"))
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    page = page.replace("__DATA__", payload.replace("</", "<\\/"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")
    print(f"wrote {output} ({len(page.encode('utf-8')) / 1e6:.1f} MB)")
    return output


def main():
    render(page_data())


if __name__ == "__main__":
    main()
