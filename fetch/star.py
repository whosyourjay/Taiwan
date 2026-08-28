"""Download 繁星推薦 錄取標準 PDFs from CAC into star/.

CAC splits the tables in two: 第一類學群至第七類學群 (one2seven) and
第八類學群 (eight, the medical schools). A college appears in eight/ only if it
admits 醫學系 that way, so a 404 there is normal.

Codes come from the per-year college list page, so a school absent that year is
skipped rather than downloaded blind.
"""

import argparse
import glob
import os
import re
import sys
import time
import urllib.error
import urllib.request
from lib.paths import source_path

OUT = source_path("star")

BASE = "https://www.cac.edu.tw/cacportal/star_his_report"
GROUPS = ("one2seven", "eight")

# The schools to fetch, or empty for every school the year lists. 陽明 and 交通
# merged into 陽明交通 for 111 admissions, so no year lists all three.
WANT = (
    "國立臺灣大學",
    "國立陽明交通大學",
    "國立政治大學",
    "國立陽明大學",
    "國立清華大學",
    "臺北醫學大學",
    "國立臺北大學",
    "國立交通大學",
)

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/126 Safari/537.36"}
# The list page wraps the name in </font> some years and </a> others.
COLLEGE = re.compile(r"\((\d{3})\)([^<]+)<")


def get(url):
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError:
        return None


def colleges(year, group):
    """{code: name} for one year and 學群 split, or {} if the page is missing."""
    page = get(f"{BASE}/{year}/{year}_result_standard/{group}/collegeList_1.php")
    if page is None:
        return {}
    return dict(COLLEGE.findall(page.decode("utf-8", "replace")))


def fetch(year, group, code):
    """Save one college's PDF; returns bytes written, or 0 if absent."""
    url = f"{BASE}/{year}/{year}_result_standard/{group}/{code}/{year}Standard_{code}.pdf"
    body = get(url)
    if not body:
        return 0
    path = os.path.join(OUT, f"{year}-{code}-{group}.pdf")
    with open(path, "wb") as f:
        f.write(body)
    return len(body)


def cached(year):
    return bool(glob.glob(os.path.join(OUT, f"{year}-*.pdf")))


def main(years, refresh=False):
    os.makedirs(OUT, exist_ok=True)
    t0, total = time.time(), 0
    for year in years:
        if cached(year) and not refresh:
            print(f"{year} cached; pass --refresh to check CAC", file=sys.stderr)
            continue
        for group in GROUPS:
            listed = colleges(year, group)
            for code, name in sorted(listed.items()):
                if WANT and name.strip() not in WANT:
                    continue
                n = fetch(year, group, code)
                total += n
                print(f"{year} {group:9} ({code}) {name.strip()}  {n:>7} bytes",
                      file=sys.stderr)
    print(f"{total} bytes in {time.time() - t0:.1f}s -> star/", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", nargs="*", default=["110"])
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    main(args.years, args.refresh)
