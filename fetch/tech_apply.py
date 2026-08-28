"""Download 四技日間部申請入學 rules and first-stage cutoff reports."""

import os
import sys

from fetch.ceec import get
from lib.paths import source_path


BASE = "https://www.jctv.ntut.edu.tw/downloads"
YEARS = tuple(str(year) for year in range(107, 115))


def urls(year):
    """Official report and program-data workbook URLs for one year."""
    root = f"{BASE}/{year}/caac"
    extension = "xlsx" if int(year) >= 113 else "xls"
    return {
        "screen": f"{root}/repot_01.pdf",
        "rules": f"{root}/{year}_caac_minute.{extension}",
    }


def main(years=YEARS):
    os.makedirs(source_path("tech"), exist_ok=True)
    for year in years:
        for kind, url in urls(year).items():
            extension = url.rsplit(".", 1)[-1]
            target = source_path(
                "tech", f"jctv-{year}-xuece-{kind}.{extension}"
            )
            if os.path.exists(target):
                print(f"exists  {target}", file=sys.stderr)
                continue
            body = get(url)
            with open(target, "wb") as f:
                f.write(body)
            print(f"{len(body):>9,}  {target}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:] or YEARS)
