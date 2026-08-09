"""Download CAP statistics and published high-school entrance cutoffs."""

import os
import sys

from fetch.ceec import get
from lib.paths import path


SOURCES = {
    "cap-107-statistics": {
        "filename": "cap-107-statistics.html",
        "url": (
            "https://www.moe.gov.tw/News_Content.aspx?n=9E7AC85F1954DDA8&"
            "s=A72AAFB92D320802&sms=169B8E91BB75571F"
        ),
    },
    "jibei-107-cutoffs": {
        "filename": "jibei-107-cutoffs.html",
        "url": (
            "https://www.tkbgo.com.tw/schoolZone/university/article/toDetail?"
            "article_id=1905"
        ),
    },
}


def main():
    outdir = path("entry")
    os.makedirs(outdir, exist_ok=True)
    for name, source in SOURCES.items():
        target = os.path.join(outdir, source["filename"])
        if os.path.exists(target):
            print(f"exists  {target}", file=sys.stderr)
            continue
        body = get(source["url"])
        with open(target, "wb") as f:
            f.write(body)
        print(f"{name:>20} {len(body):>9,}  {target}", file=sys.stderr)


if __name__ == "__main__":
    main()
