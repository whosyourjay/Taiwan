"""Download 個人申請 篩選標準 images from CAC into apply/.

CAC publishes this table only as a PNG per college, one tall image holding the
whole school. There is no index page, but the 個人申請 and 繁星 archives share
CAC's 3-digit college codes, so the 繁星 list resolves a code to a name.

Writes apply/colleges.tsv so parse_apply.py needs no network.
"""

import os
import sys
import time

from fetch_star import WANT, colleges, get

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "apply")

BASE = "https://www.cac.edu.tw/cacportal/apply_his_report"


def main(years):
    os.makedirs(OUT, exist_ok=True)
    t0, total, seen = time.time(), 0, []
    for year in years:
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
            seen.append((year, code, name))
            print(f"{year} ({code}) {name}  {len(body):>8} bytes", file=sys.stderr)
    with open(os.path.join(OUT, "colleges.tsv"), "w", encoding="utf-8") as f:
        f.write("year\tcollege_code\tcollege\n")
        for row in seen:
            f.write("\t".join(row) + "\n")
    print(f"{total} bytes in {time.time() - t0:.1f}s -> apply/", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:] or ["110", "111"])
