"""Download 繁星推薦 錄取標準 PDFs from CAC into star/.

CAC splits the tables in two: 第一類學群至第七類學群 (one2seven) and
第八類學群 (eight, the medical schools). A college appears in eight/ only if it
admits 醫學系 that way, so a 404 there is normal.

Codes come from the per-year college list page, so a school absent that year is
skipped rather than downloaded blind. The list pages, PDFs, and a completion
marker all stay local; a completed year makes no network requests on a warm run.
"""

import argparse
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

WANT = ()

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
    cached_page = os.path.join(OUT, f"{year}-{group}-colleges.html")
    if os.path.exists(cached_page):
        with open(cached_page, "rb") as handle:
            page = handle.read()
    else:
        page = get(f"{BASE}/{year}/{year}_result_standard/{group}/collegeList_1.php")
        if page:
            with open(cached_page, "wb") as handle:
                handle.write(page)
    if page is None:
        return {}
    return dict(COLLEGE.findall(page.decode("utf-8", "replace")))


def fetch(year, group, code):
    """Save one college's PDF; returns bytes written, or 0 if absent."""
    path = os.path.join(OUT, f"{year}-{code}-{group}.pdf")
    if os.path.exists(path):
        return 0
    url = f"{BASE}/{year}/{year}_result_standard/{group}/{code}/{year}Standard_{code}.pdf"
    body = get(url)
    if not body:
        return None
    with open(path, "wb") as f:
        f.write(body)
    return len(body)


def cached(year):
    return os.path.exists(os.path.join(OUT, f"{year}.complete"))


def mark_complete(year):
    with open(os.path.join(OUT, f"{year}.complete"), "w", encoding="ascii") as handle:
        handle.write("all colleges listed by CAC downloaded\n")


def main(years, refresh=False):
    os.makedirs(OUT, exist_ok=True)
    t0, total = time.time(), 0
    for year in years:
        if cached(year) and not refresh:
            print(f"{year} cached; pass --refresh to check CAC", file=sys.stderr)
            continue
        complete = True
        for group in GROUPS:
            listed = colleges(year, group)
            complete &= bool(listed) or group == "eight"
            for code, name in sorted(listed.items()):
                if WANT and name.strip() not in WANT:
                    continue
                n = fetch(year, group, code)
                complete &= n is not None
                total += n or 0
                size = "absent" if n is None else f"{n:>7} bytes"
                print(f"{year} {group:9} ({code}) {name.strip()}  {size}",
                      file=sys.stderr)
        if complete and not WANT:
            mark_complete(year)
    print(f"{total} bytes in {time.time() - t0:.1f}s -> star/", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("years", nargs="*", default=["110"])
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    main(args.years, args.refresh)
