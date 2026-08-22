"""Download the Tongce report used to estimate the age-cohort test pool."""

import os
import sys

from fetch.ceec import get
from lib.paths import source_path


REPORTS = {
    "tcte-110-work-report.pdf": (
        "https://www.tcte.edu.tw/index.php?mod=TVETest%2Fopendata4y%2Fyt%2F110%2Ffn%2F"
        "110%E5%AD%B8%E5%B9%B4%E5%BA%A6%E7%B5%B1%E4%B8%80%E5%85%A5%E5%AD%B8%E6%B8%AC%E9%A9%97"
        "%E5%B7%A5%E4%BD%9C%E5%A0%B1%E5%91%8A.pdf"
    ),
}


def main():
    outdir = source_path("tech")
    os.makedirs(outdir, exist_ok=True)
    for name, url in REPORTS.items():
        target = os.path.join(outdir, name)
        if os.path.exists(target):
            print(f"exists  {target}", file=sys.stderr)
            continue
        body = get(url)
        with open(target, "wb") as f:
            f.write(body)
        print(f"{len(body):>9,}  {target}", file=sys.stderr)


if __name__ == "__main__":
    main()
