"""Download every document found by the high-school entry-report audit."""

import argparse
import concurrent.futures
import hashlib
import os
import sys
import urllib.parse

from fetch.high_school_entry_audit import request, short_error
from lib import tsvio
from lib.paths import data_path, source_path


INPUT = data_path("high-school-entry-report-candidates.tsv")
OUTDIR = source_path("high-school-entry-reports")
MANIFEST = os.path.join(OUTDIR, "manifest.tsv")
MANIFEST_COLUMNS = (
    "document_url",
    "final_url",
    "filename",
    "status",
    "bytes",
    "sha256",
    "error",
)
SUFFIXES = {".pdf", ".doc", ".docx", ".odt", ".xls", ".xlsx"}


def filename(url):
    suffix = os.path.splitext(urllib.parse.urlsplit(url).path)[1].lower()
    suffix = suffix if suffix in SUFFIXES else ".bin"
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24] + suffix


def digest(body):
    return hashlib.sha256(body).hexdigest()


def cached_row(url, target):
    with open(target, "rb") as handle:
        body = handle.read()
    return {
        "document_url": url,
        "final_url": url,
        "filename": os.path.basename(target),
        "status": "cached",
        "bytes": len(body),
        "sha256": digest(body),
        "error": "",
    }


def download(url, args):
    name = filename(url)
    target = os.path.join(args.outdir, name)
    if os.path.exists(target):
        return cached_row(url, target)
    error = ""
    for _ in range(args.retries + 1):
        try:
            body, final_url = request(
                url, args.timeout, max_body=args.max_bytes
            )
            temporary = target + ".part"
            with open(temporary, "wb") as handle:
                handle.write(body)
            os.replace(temporary, target)
            return {
                "document_url": url,
                "final_url": final_url,
                "filename": name,
                "status": "ok",
                "bytes": len(body),
                "sha256": digest(body),
                "error": "",
            }
        except Exception as exc:
            error = short_error(exc)
    return {
        "document_url": url,
        "final_url": "",
        "filename": name,
        "status": "failed",
        "bytes": 0,
        "sha256": "",
        "error": error,
    }


def write_manifest(path, rows):
    from fetch.high_school_entry_audit import write_rows
    write_rows(path, MANIFEST_COLUMNS, rows)


def run(args):
    if not args.refresh and os.path.exists(args.manifest):
        rows = list(tsvio.read_rows(args.manifest))
        print("using cached document manifest; pass --refresh to retry downloads",
              file=sys.stderr)
        summarize(rows, args.manifest)
        return
    os.makedirs(args.outdir, exist_ok=True)
    urls = sorted({row["document_url"] for row in tsvio.read_rows(args.input)})
    rows = []
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.workers) as executor:
        futures = {executor.submit(download, url, args): url for url in urls}
        for done, future in enumerate(
                concurrent.futures.as_completed(futures), 1):
            rows.append(future.result())
            if done % 25 == 0 or done == len(urls):
                failures = sum(row["status"] == "failed" for row in rows)
                print(f"{done:>4}/{len(urls)} documents; {failures} failed",
                      file=sys.stderr)
    rows.sort(key=lambda row: row["document_url"])
    write_manifest(args.manifest, rows)
    summarize(rows, args.manifest)


def summarize(rows, manifest):
    failures = sum(row["status"] == "failed" for row in rows)
    total = sum(int(row["bytes"] or 0) for row in rows)
    print(f"{len(rows)} rows in {manifest}", file=sys.stderr)
    print(f"{total:,} bytes; {failures} failed", file=sys.stderr)


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=INPUT)
    parser.add_argument("--outdir", default=OUTDIR)
    parser.add_argument("--manifest", default=MANIFEST)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--retries", type=int, default=1)
    parser.add_argument("--max-bytes", type=int, default=50_000_000)
    parser.add_argument("--refresh", action="store_true",
                        help="retry URLs instead of trusting the saved manifest")
    args = parser.parse_args(argv)
    if (args.workers < 1 or args.timeout <= 0 or args.retries < 0 or
            args.max_bytes < 1):
        parser.error("numeric options must be positive")
    return args


if __name__ == "__main__":
    run(arguments())
