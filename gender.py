"""Department gender balance from 教育部統計處 大專校院各校科系別學生數.

An independent source from the admission cutoffs: it counts who is enrolled, not
who was admitted. Ratios use total bachelor headcount rather than the first-year
row, since pooling four cohorts steadies small departments.

    https://stats.moe.gov.tw/files/detail/{year}/{year}_students.csv
"""

import collections
import csv
import os
import urllib.request

from deptname import key

HERE = os.path.dirname(__file__)
CSV = os.path.join(HERE, "moe", "{year}_students.csv")
URL = "https://stats.moe.gov.tw/files/detail/{year}/{year}_students.csv"
LATEST = "113"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def fetch(year=LATEST):
    path = CSV.format(year=year)
    if os.path.exists(path):
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    req = urllib.request.Request(URL.format(year=year), headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    with open(path, "wb") as f:
        f.write(data)
    return path


def load(year=LATEST):
    """Map (校名, normalised 系名) -> (men, women) for day-division bachelors."""
    with open(fetch(year), encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    out = collections.defaultdict(lambda: [0, 0])
    for row in rows:
        if not row["等級別"].startswith("B") or not row["日間∕進修別"].startswith("D"):
            continue
        dept = (row["學校名稱"], key(row["科系名稱"]))
        out[dept][0] += int(row["男生計"])
        out[dept][1] += int(row["女生計"])
    return out


def lookup(table, school, dept):
    """(men, women) for a department, or None when 教育部 has no matching row."""
    return table.get((school, key(dept)))


def school_totals(table):
    out = collections.defaultdict(lambda: [0, 0])
    for (school, _), (men, women) in table.items():
        out[school][0] += men
        out[school][1] += women
    return out


if __name__ == "__main__":
    table = load()
    print(f"{len(table)} departments, {len(school_totals(table))} schools")
