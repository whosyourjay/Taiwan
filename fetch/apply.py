"""Download 個人申請 篩選標準 images from CAC into apply/.

CAC publishes this table only as a PNG per college, one tall image holding the
whole school. There is no index page, but the 個人申請 and 繁星 archives share
CAC's 3-digit college codes, so the 繁星 list resolves a code to a name.

Writes apply/colleges.tsv so `python -m parse.apply` needs no network.
"""

import argparse
import csv
import glob
import os
import sys
import time

from fetch.star import WANT, colleges, get
from lib.paths import source_path

OUT = source_path("apply")

BASE = "https://www.cac.edu.tw/cacportal/apply_his_report"


def cached(year):
    return bool(glob.glob(os.path.join(OUT, f"{year}-*.png")))


def known_colleges(path):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        return {(row["year"], row["college_code"]): row["college"]
                for row in csv.DictReader(handle, delimiter="\t")}


def main(years, refresh=False):
    os.makedirs(OUT, exist_ok=True)
    college_path = os.path.join(OUT, "colleges.tsv")
    t0, total, seen = time.time(), 0, known_colleges(college_path)
    for year in years:
        if cached(year) and not refresh:
            print(f"{year} cached; pass --refresh to check CAC", file=sys.stderr)
            continue
        listed = {c: n.strip() for c, n in colleges(year, "one2seven").items()}
        for code, name in sorted(listed.items()):
            if WANT and name not in WANT:
                continue
            body = get(f"{BASE}/{year}/{year}_sieve_standard/report/pict/{code}.png")
            if not body:
                print(f"{year} ({code}) {name}  absent", file=sys.stderr)
                continue
            with open(os.path.join(OUT, f"{year}-{code}.png"), "wb") as f:
                f.write(body)
            total += len(body)
            seen[(year, code)] = name
            print(f"{year} ({code}) {name}  {len(body):>8} bytes", file=sys.stderr)
    with open(college_path, "w", encoding="utf-8") as f:
        f.write("year\tcollege_code\tcollege\n")
        for (year, code), name in sorted(seen.items()):
            f.write(f"{year}\t{code}\t{name}\n")
    print(f"{total} bytes in {time.time() - t0:.1f}s -> apply/", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", nargs="*", default=["110", "111"])
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    main(args.years, args.refresh)
