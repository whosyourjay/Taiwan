"""Download 110 四技日間部申請入學 rules and first-stage cutoff report."""

import os
import sys

from fetch.ceec import get
from lib.paths import path


BASE = "https://www.jctv.ntut.edu.tw/downloads"
YEAR = "110"


def urls(year):
    """Official report and program-data workbook URLs for one year."""
    root = f"{BASE}/{year}/caac"
    return {
        "screen": f"{root}/repot_01.pdf",
        "rules": f"{root}/{year}_caac_minute.xls",
    }


def main():
    os.makedirs(path("tech"), exist_ok=True)
    for kind, url in urls(YEAR).items():
        extension = url.rsplit(".", 1)[-1]
        target = path("tech", f"jctv-{YEAR}-xuece-{kind}.{extension}")
        if os.path.exists(target):
            print(f"exists  {target}", file=sys.stderr)
            continue
        body = get(url)
        with open(target, "wb") as f:
            f.write(body)
        print(f"{len(body):>9,}  {target}", file=sys.stderr)


if __name__ == "__main__":
    main()
