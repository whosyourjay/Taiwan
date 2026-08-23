"""Download CAP statistics and published high-school entrance cutoffs."""

import os
import sys

from fetch.ceec import get
from lib.paths import path, source_path


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
    "educatorfocus-114-cutoffs": {
        "filename": "educatorfocus-114-cutoffs.html",
        "url": "https://www.educatorfocus.com.tw/News/Detail/259CB02831E311C9",
    },
    "moe-115-entry-districts": {
        "filename": "moe-115-entry-districts.pdf",
        "url": (
            "https://www.k12ea.gov.tw/Tw/Common/Downloader?"
            "id=c73b8a82-f1d4-4d59-a8db-8127c8c2708e"
        ),
    },
    "moe-115-entry-results": {
        "filename": "moe-115-entry-results.pdf",
        "url": (
            "https://www.k12ea.gov.tw/Tw/Common/Downloader?"
            "id=c42e6598-19d0-4b24-8c47-b5f7c9c9ed5c"
        ),
    },
}


def main():
    outdir = source_path("entry")
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
