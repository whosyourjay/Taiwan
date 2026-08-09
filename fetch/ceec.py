"""Download CEEC statistics PDFs for 學測 (GSAT) and 分科測驗/指考."""

import os
import re
import urllib.parse
import urllib.request
from lib.paths import path as repo_path

BASE = "https://www.ceec.edu.tw"
INDEXES = {
    "xuece": "0J018604485538810196",  # 學科能力測驗 統計資料
    "zhikao": "0J018611000723433352",  # 分科測驗(110前指考) 統計資料
}
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


def get(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def year_pages(index_id):
    """Return (title, url) for every year's statistics page across all index pages."""
    seen = {}
    for page in range(1, 6):
        url = f"{BASE}/xmdoc?xsmsid={index_id}&page={page}"
        html = get(url).decode("utf-8", "replace")
        found = re.findall(
            r'href="(/xmdoc/cont\?xsmsid=' + index_id + r'&sid=[^"]+)"[^>]*>([^<]+)<', html
        )
        if not found:
            break
        for href, title in found:
            seen.setdefault(BASE + href.replace("&amp;", "&"), title.strip())
    return seen


def data_links(page_url):
    """Return absolute URLs of the statistics files attached to a year's page."""
    html = get(page_url).decode("utf-8", "replace")
    links = re.findall(r'href="((?:https://www\.ceec\.edu\.tw)?/files/file_pool/[^"]+)"', html)
    out = []
    for link in links:
        if not link.startswith("http"):
            link = BASE + link
        name = urllib.parse.unquote(link.rsplit("/", 1)[-1])
        # Skip site-wide boilerplate attachments that appear in the page chrome.
        if re.match(r"^\d", name) and link not in out:
            out.append(link)
    return out


def main():
    for exam, index_id in INDEXES.items():
        outdir = repo_path("ceec", exam)
        os.makedirs(outdir, exist_ok=True)
        for page_url, title in year_pages(index_id).items():
            year = re.match(r"(\d+)", title)
            year = year.group(1) if year else "unknown"
            for i, link in enumerate(data_links(page_url)):
                name = urllib.parse.unquote(link.rsplit("/", 1)[-1])
                name = re.sub(r"[^\w.一-鿿-]", "_", name)[-80:]
                target = os.path.join(outdir, f"{year}-{i:02d}-{name}")
                if os.path.exists(target):
                    continue
                try:
                    data = get(link)
                except Exception as e:
                    print("FAIL", link, e)
                    continue
                with open(target, "wb") as f:
                    f.write(data)
                print(f"{len(data):>9,}  {target}")


if __name__ == "__main__":
    main()
