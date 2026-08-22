#!/usr/bin/env python3
"""Write each Taiwan admission allocation with its modeled ability and route."""

from collections import defaultdict

from lib import tsvio
from lib.paths import data_path, ranking_path
from pool import ability
from pool import fit


TARGET = ranking_path("route_ability.tsv")
FIELDS = ("family", "route", "ability", "seats")
ROUTES = {
    "uac": ("Exam score", "一般大學 分發入學"),
    "tech": ("Exam score", "四技二專 聯合登記分發"),
    "star": ("Combined score", "一般大學 繁星推薦"),
    # Every remaining path screens on 學測 or 統測 before it interviews anyone,
    # and that screen is the score measured here.
    "star_eight": ("Combined score", "繁星推薦 第八類"),
    "apply": ("Exam score", "一般大學 申請入學"),
    "tech_apply": ("Exam score", "科技校院 甄選 / 申請入學"),
}
TOTAL_PATH = {"star_eight": "star", "tech_apply": "tech_select"}


def rows():
    """Score each raw allocation before pooling routes inside a department."""
    admissions, splines = ability.curves()
    targets = {
        row["path"]: float(row["admitted"])
        for row in tsvio.read_rows(data_path("admission-totals.tsv"))
        if row["year"] == fit.YEAR
    }
    covered = defaultdict(float)
    for row, _, level, seats in ability.read(admissions, splines):
        try:
            family, route = ROUTES[row["path"]]
        except KeyError as error:
            raise ValueError(f"unclassified Taiwan path: {row['path']}") from error
        count = float(seats)
        covered[TOTAL_PATH.get(row["path"], row["path"])] += count
        yield {"family": family, "route": route,
               "ability": round(100 * level, 3), "seats": count}
    for path, target in targets.items():
        missing = max(target - covered[path], 0.0)
        if missing:
            route_path = "tech_apply" if path == "tech_select" else path
            family, route = ROUTES[route_path]
            yield {"family": family, "route": route,
                   "ability": 0.0, "seats": missing}


def main():
    found = list(rows())
    print(f"wrote {tsvio.write_rows(TARGET, found):,} allocations to {TARGET}")


if __name__ == "__main__":
    main()
