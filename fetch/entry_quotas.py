"""Download each 就學區's published 免試入學 admission quotas.

The districts share one platform, so a single crawl reaches every one that
answers: a portal names its own application code, the announcement list names
the quota notice, and that notice carries a file of 名額 by school and 科別.
Those counts are the entrant totals that turn a school's cutoff into a share of
the district rather than a bare score.
"""

import argparse
import concurrent.futures
import os
import re
import socket
import ssl
import sys
import urllib.parse
import urllib.request

from lib import tsvio
from lib.paths import data_path, source_path

DISTRICTS = "entry-districts.tsv"
OUTDIR = "entry-quotas"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
WANTED = "名額"
PROBE_TIMEOUT = 5
TIMEOUT = 45
WORKERS = 2
APP = "{host}/NoExamImitate_{code}/NoExamImitate/Apps"
NEWS = APP + "/Page/Public/News.aspx"
GETFILE = APP + "/Action/GetFile.ashx"
LINK = re.compile(r'<a[^>]*href="News\.aspx\?SEQNO=(\d+)"[^>]*>(.*?)</a>', re.S)
ATTACHED = re.compile(r'GetFile\.ashx\?SEQNO=(\d+)&(?:amp;)?FILE=([^"&]+)"')
TAGS = re.compile(r"<[^>]+>")
# Government hosts serve incomplete chains, and nothing here is a secret.
LAX = ssl.create_default_context()
LAX.check_hostname = False
LAX.verify_mode = ssl.CERT_NONE


def get(url):
    request = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(request, timeout=TIMEOUT, context=LAX) as response:
        return response.read()


def page(url):
    return get(url).decode("utf-8", "replace")


def answers(host):
    """Whether a host completes a connection, so a dead one costs seconds not minutes."""
    name = urllib.parse.urlparse(host).hostname
    try:
        socket.create_connection((name, 443), timeout=PROBE_TIMEOUT).close()
        return True
    except OSError:
        return False


def app_code(host):
    """The platform's code for one district, named by that district's own portal."""
    found = re.search(r"/NoExamImitate_([A-Z]+)/", page(host))
    if not found:
        raise ValueError("portal names no application code")
    return found.group(1)


def listed(body):
    """Announcement numbers and titles carried on one list page."""
    return {int(number): TAGS.sub("", title).strip()
            for number, title in LINK.findall(body)}


def announcements(host, code):
    """Every announcement, walking the numbers when the list runs past one page."""
    url = NEWS.format(host=host, code=code)
    found = listed(page(url))
    pages = re.search(r"ddlPageIndex.*?</select>", page(url), re.S)
    if found and pages and len(re.findall("<option", pages.group(0))) > 1:
        for number in range(1, max(found) + 1):
            if number not in found:
                found[number] = listed(f"{url}?SEQNO={number}").get(number, "")
    return found


def attachments(host, code, number):
    """Platform-hosted files on one announcement, as (filename, url)."""
    body = page(f"{NEWS.format(host=host, code=code)}?SEQNO={number}")
    out = {}
    for seqno, name in ATTACHED.findall(body):
        name = urllib.parse.unquote(name)
        out[name] = (f"{GETFILE.format(host=host, code=code)}"
                     f"?SEQNO={seqno}&FILE={urllib.parse.quote(name)}")
    return out


def save(outdir, prefix, name, url):
    """Fetch one attachment unless it is already on disk; return its path."""
    target = os.path.join(outdir, f"{prefix}-{name.replace(os.sep, '_')}")
    if not os.path.exists(target):
        with open(target, "wb") as handle:
            handle.write(get(url))
    return target


def district_files(row, outdir):
    """Download every quota file one district publishes."""
    host, prefix = row["host"], urllib.parse.urlparse(row["host"]).hostname.split(".")[0]
    if not answers(host):
        return row["district"], "unreachable", []
    try:
        code = app_code(host)
        found = announcements(host, code)
    except Exception as error:  # noqa: BLE001 - one bad district must not stop the rest
        return row["district"], f"failed: {type(error).__name__}", []
    saved = []
    for number, title in sorted(found.items(), reverse=True):
        if WANTED not in title:
            continue
        for name, url in attachments(host, code, number).items():
            saved.append((title, name, save(outdir, prefix, name, url)))
    return row["district"], f"{len(found)} announcements", saved


def populated(directory):
    if not os.path.isdir(directory):
        return False
    with os.scandir(directory) as entries:
        return any(not entry.name.startswith(".") for entry in entries)


def main(refresh=False):
    rows = list(tsvio.read_rows(data_path(DISTRICTS)))
    outdir = source_path(OUTDIR)
    os.makedirs(outdir, exist_ok=True)
    if populated(outdir) and not refresh:
        print(f"cached quota files in {outdir}; pass --refresh to check upstream",
              file=sys.stderr)
        return 0
    with concurrent.futures.ThreadPoolExecutor(WORKERS) as pool:
        results = list(pool.map(lambda row: district_files(row, outdir), rows))
    total = 0
    for district, note, saved in results:
        print(f"{district:<8}{note}", file=sys.stderr)
        for title, name, target in saved:
            total += 1
            print(f"         {title[:30]:<32}{name[:40]:<42}{target}", file=sys.stderr)
    print(f"\n{total} quota files from {len(rows)} districts", file=sys.stderr)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true")
    sys.exit(main(parser.parse_args().refresh))
