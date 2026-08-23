"""Download published high-school university-destination tables."""

import os
import sys

from fetch.ceec import get
from lib.paths import path, source_path


SOURCES = {
    "110": {
        "high_school": "臺北市立第一女子高級中學",
        "filename": "fg-110-destinations.pdf",
        "url": (
            "https://www.fg.tp.edu.tw/wp-content/uploads/doc/curricula/"
            "111%E5%AD%B8%E6%A0%A1%E6%97%A5%E6%89%8B%E5%86%8A.pdf"
        ),
    },
}


# Every school's roll and last year's graduates, which turn a destination count
# into a share of the school that produced it.
SIZES = {
    "dir": "moe",
    "filename": "moe-high-school-base.csv",
    "url": "https://stats.moe.gov.tw/files/opendata/base0.csv",
}
# 繁星 admits per high school, gathered from school 榜單 and news reports and
# openly still filling in, so a school's absence means nobody has filed it
# rather than that it placed nobody.
STAR_COUNTS = {
    "dir": "high-school",
    "filename": "star-school-counts-114.html",
    "url": "https://shirley.tw/114y-star-plan/",
}


def download(source, default_dir):
    outdir = source_path(source.get("dir", default_dir))
    os.makedirs(outdir, exist_ok=True)
    target = os.path.join(outdir, source["filename"])
    if os.path.exists(target):
        print(f"exists  {target}", file=sys.stderr)
        return
    body = get(source["url"])
    with open(target, "wb") as f:
        f.write(body)
    print(f"{len(body):>9,}  {target}", file=sys.stderr)


def main():
    for source in list(SOURCES.values()) + [SIZES, STAR_COUNTS]:
        download(source, "high-school")


if __name__ == "__main__":
    main()
