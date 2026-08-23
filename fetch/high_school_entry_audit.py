"""Audit school websites for published high-school entrance distributions.

The Ministry of Education school directory supplies the sites.  NSS sites have
a public full-text endpoint that returns pages and their attachments; other
sites get a cheap sitemap probe so later crawlers can be chosen from measured
CMS coverage instead of search-engine results.
"""

import argparse
import concurrent.futures
import csv
import html
from html.parser import HTMLParser
import json
import math
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request

from lib.paths import data_path


DIRECTORY_YEAR = "115"
DIRECTORY_URL = (
    f"https://stats.moe.gov.tw/files/school/{DIRECTORY_YEAR}/high.json"
)
KEYWORDS = ("優質化", "學校經營計畫", "中長程計畫", "新生入學")
CANDIDATE_TERMS = KEYWORDS + ("新生", "會考", "入學情形", "學校計畫")
DOCUMENT_SUFFIXES = (".pdf", ".doc", ".docx", ".odt", ".xls", ".xlsx")
USER_AGENT = "Taiwan-admission-research/1.0"
PAGE_SIZE = 50
MAX_BODY = 8_000_000
SSL_CONTEXT = ssl.create_default_context()
# Python 3.14 enables RFC 5280 strict mode, but stats.moe.gov.tw's otherwise
# valid chain omits a legacy Subject Key Identifier.  Keep CA and hostname
# checks while matching curl/browser handling of that certificate.
SSL_CONTEXT.verify_flags &= ~ssl.VERIFY_X509_STRICT

COVERAGE_COLUMNS = (
    "year",
    "school_code",
    "high_school",
    "ownership",
    "city",
    "official_url",
    "resolved_url",
    "reachable",
    "discovery",
    "search_results",
    "candidate_documents",
    "truncated_queries",
    "sitemap_url",
    "error",
)
CANDIDATE_COLUMNS = (
    "year",
    "school_code",
    "high_school",
    "city",
    "discovery",
    "keywords",
    "page_title",
    "document_name",
    "document_url",
)


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.href = None
        self.label = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            self.href = dict(attrs).get("href")
            self.label = []

    def handle_data(self, data):
        if self.href:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.href:
            self.links.append((self.href, "".join(self.label).strip()))
            self.href = None
            self.label = []


def request(url, timeout, data=None, max_body=MAX_BODY):
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    if data is not None:
        data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(
            req, timeout=timeout, context=SSL_CONTEXT) as response:
        if max_body is None:
            return b"", response.geturl()
        body = response.read(max_body + 1)
        if len(body) > max_body:
            raise ValueError(f"response exceeds {max_body:,} bytes")
        return body, response.geturl()


def directory_rows(url, timeout):
    body, _ = request(url, timeout)
    rows = json.loads(body.decode("utf-8-sig"))
    required = {"學年度", "代碼", "學校名稱", "網址"}
    if not isinstance(rows, list) or not rows or not required <= set(rows[0]):
        raise ValueError("unexpected MOE school-directory schema")
    return rows


def clean_city(value):
    return re.sub(r"^\[\d+\]", "", value or "")


def normalize_url(value):
    value = (value or "").strip()
    if not value:
        return ""
    if "://" not in value:
        value = "https://" + value
    parsed = urllib.parse.urlsplit(value)
    return urllib.parse.urlunsplit(
        (parsed.scheme.lower(), parsed.netloc, parsed.path or "/", parsed.query, "")
    )


def url_origin(url):
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def site_variants(url):
    if not url:
        return []
    parsed = urllib.parse.urlsplit(url)
    variants = [url]
    if parsed.scheme == "http":
        variants.insert(0, urllib.parse.urlunsplit(("https", *parsed[1:])))
    return list(dict.fromkeys(variants))


def resolve_site(url, timeout):
    errors = []
    for candidate in site_variants(url):
        try:
            _, resolved = request(candidate, timeout, max_body=None)
            return resolved, ""
        except Exception as exc:  # Each site must remain one audit row.
            errors.append(f"{candidate}: {short_error(exc)}")
    return "", "; ".join(errors)


def short_error(exc):
    if isinstance(exc, urllib.error.HTTPError):
        return f"HTTP {exc.code}"
    if isinstance(exc, urllib.error.URLError):
        return str(exc.reason)
    return str(exc)


def nss_page(origin, keyword, page, timeout):
    body, final_url = request(
        origin + "/nss/ext/fulltext",
        timeout,
        {
            "keyword": keyword,
            "each": PAGE_SIZE,
            "page": page,
            "partten": "",
            "searchRange": "",
        },
    )
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("not an NSS full-text response")
    data = payload.get("data")
    if payload.get("error") != 0 or not isinstance(data, dict):
        raise ValueError("not an NSS full-text response")
    if not isinstance(data.get("result"), list):
        raise ValueError("NSS response has no result list")
    return data, url_origin(final_url)


def document_link(url, name=""):
    path = urllib.parse.urlsplit(url).path.lower()
    label = name.lower()
    return path.endswith(DOCUMENT_SUFFIXES) or label.endswith(DOCUMENT_SUFFIXES)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from strings(item)


def links_from_result(result, origin):
    data = result.get("data", {})
    links = []
    for source, entries in (("attachment", data.get("ext", [])),
                            ("page_link", data.get("links", []))):
        for entry in entries or []:
            if not isinstance(entry, dict) or not entry.get("url"):
                continue
            name = " ".join(strings(entry.get("name", "")))
            links.extend((source, name, url) for url in strings(entry["url"]))
    parser = LinkParser()
    parser.feed("\n".join(strings(data.get("content", ""))))
    links.extend(("page_html", name, link) for link, name in parser.links)

    found = []
    for source, name, link in links:
        absolute = urllib.parse.urljoin(origin + "/", html.unescape(link))
        if document_link(absolute, name):
            found.append((source, name or os.path.basename(
                urllib.parse.urlsplit(absolute).path), absolute))
    return found


def add_nss_results(documents, results, school, origin, keyword):
    for result in results:
        data = result.get("data") if isinstance(result, dict) else None
        title = " ".join(strings(
            data.get("name", "") if isinstance(data, dict) else ""
        )).strip()
        if not title and isinstance(result, dict):
            title = next(strings(result.get("keyword", "")), "").strip()
        for _, name, url in links_from_result(result, origin):
            key = url.split("#", 1)[0]
            row = documents.setdefault(key, {
                "year": school["學年度"],
                "school_code": school["代碼"],
                "high_school": school["學校名稱"],
                "city": clean_city(school.get("縣市名稱")),
                "discovery": "nss",
                "keywords": set(),
                "page_title": title,
                "document_name": name,
                "document_url": key,
            })
            row["keywords"].add(keyword)


def search_nss(origin, school, keywords, max_results, timeout, first):
    documents = {}
    total_results = 0
    truncated = []
    errors = []
    current_origin = origin
    for index, keyword in enumerate(keywords):
        try:
            data, current_origin = first if index == 0 else nss_page(
                current_origin, keyword, 1, timeout
            )
            count = int(data.get("count", len(data["result"])))
            total_results += count
            add_nss_results(documents, data["result"], school,
                            current_origin, keyword)
            pages = math.ceil(min(count, max_results) / PAGE_SIZE)
            for page in range(2, pages + 1):
                data, current_origin = nss_page(
                    current_origin, keyword, page, timeout
                )
                add_nss_results(documents, data["result"], school,
                                current_origin, keyword)
            if count > max_results:
                truncated.append(keyword)
        except Exception as exc:
            errors.append(f"{keyword}: {short_error(exc)}")
    rows = list(documents.values())
    for row in rows:
        row["keywords"] = ",".join(sorted(row["keywords"]))
    return total_results, rows, truncated, errors, current_origin


def sitemap_urls(origin, timeout, max_sitemaps=20):
    declared = []
    errors = []
    try:
        body, _ = request(origin + "/robots.txt", timeout, max_body=500_000)
        text = body.decode("utf-8", "replace")
        declared = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", text)
    except Exception as exc:
        errors.append(f"robots: {short_error(exc)}")
    queue = declared or [origin + "/sitemap.xml"]
    seen = set()
    locations = []
    while queue and len(seen) < max_sitemaps:
        sitemap = queue.pop(0)
        if sitemap in seen:
            continue
        seen.add(sitemap)
        try:
            body, final = request(sitemap, timeout)
            if b"<urlset" not in body and b"<sitemapindex" not in body:
                raise ValueError("not a sitemap")
            got = [html.unescape(value.decode("utf-8", "replace").strip())
                   for value in re.findall(
                       rb"<loc[^>]*>(.*?)</loc>", body, re.I | re.S
                   )]
            locations.extend(value for value in got if document_link(value))
            queue.extend(value for value in got if value.lower().endswith(
                (".xml", ".xml.gz")
            ))
            if not declared:
                declared = [final]
        except Exception as exc:
            errors.append(f"sitemap {sitemap}: {short_error(exc)}")
    return declared, sorted(set(locations)), errors


def sitemap_candidates(school, urls):
    urls = [url for url in urls if any(
        term in urllib.parse.unquote(url) for term in CANDIDATE_TERMS
    )]
    return [{
        "year": school["學年度"],
        "school_code": school["代碼"],
        "high_school": school["學校名稱"],
        "city": clean_city(school.get("縣市名稱")),
        "discovery": "sitemap",
        "keywords": "",
        "page_title": "",
        "document_name": urllib.parse.unquote(os.path.basename(
            urllib.parse.urlsplit(url).path
        )),
        "document_url": url,
    } for url in urls]


def audit_school(school, args):
    official = normalize_url(school.get("網址"))
    resolved, resolve_error = resolve_site(official, args.timeout)
    origins = []
    for value in (resolved, *site_variants(official)):
        if value:
            origins.append(url_origin(value))
    origins = list(dict.fromkeys(origins))
    errors = [resolve_error] if resolve_error else []

    for origin in origins:
        try:
            first = nss_page(origin, args.keywords[0], 1, args.timeout)
        except Exception as exc:
            errors.append(f"NSS {origin}: {short_error(exc)}")
            continue
        total, documents, truncated, search_errors, final_origin = search_nss(
            first[1], school, args.keywords, args.max_results, args.timeout,
            first,
        )
        errors.extend(search_errors)
        return coverage_row(
            school, official, resolved or final_origin, bool(resolved), "nss",
            total, len(documents), truncated, "", errors,
        ), documents

    if origins:
        sitemaps, urls, sitemap_errors = sitemap_urls(origins[0], args.timeout)
        errors.extend(sitemap_errors)
    else:
        sitemaps, urls = [], []
    discovery = "sitemap" if sitemaps else "none"
    documents = sitemap_candidates(school, urls)
    return coverage_row(
        school, official, resolved, bool(resolved), discovery, 0,
        len(documents), [], ",".join(sitemaps), errors,
    ), documents


def coverage_row(school, official, resolved, reachable, discovery,
                 results, documents, truncated, sitemap, errors):
    return {
        "year": school["學年度"],
        "school_code": school["代碼"],
        "high_school": school["學校名稱"],
        "ownership": school.get("公/私立", ""),
        "city": clean_city(school.get("縣市名稱")),
        "official_url": official,
        "resolved_url": resolved,
        "reachable": int(reachable),
        "discovery": discovery,
        "search_results": results,
        "candidate_documents": documents,
        "truncated_queries": ",".join(truncated),
        "sitemap_url": sitemap,
        "error": "; ".join(error for error in errors if error),
    }


def clean_field(value):
    if isinstance(value, str):
        return re.sub(r"[\t\r\n]+", " ", value).strip()
    return value


def write_rows(filename, columns, rows):
    directory = os.path.dirname(os.path.abspath(filename))
    os.makedirs(directory, exist_ok=True)
    with open(filename, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, columns, delimiter="\t",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: clean_field(value) for key, value in row.items()}
                         for row in rows)


def select_schools(rows, codes, limit):
    if codes:
        wanted = set(codes)
        rows = [row for row in rows if row["代碼"] in wanted]
        missing = wanted - {row["代碼"] for row in rows}
        if missing:
            raise ValueError("school codes absent from directory: " +
                             ", ".join(sorted(missing)))
    return rows[:limit] if limit else rows


def run(args):
    schools = select_schools(
        directory_rows(args.directory_url, args.timeout),
        args.school_code,
        args.limit,
    )
    results = []
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.workers) as executor:
        futures = {executor.submit(audit_school, school, args): school
                   for school in schools}
        for done, future in enumerate(
                concurrent.futures.as_completed(futures), 1):
            school = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                row = coverage_row(
                    school, normalize_url(school.get("網址")), "", False,
                    "none", 0, 0, [], "", [short_error(exc)],
                )
                results.append((row, []))
            print(f"{done:>4}/{len(schools)}  {school['代碼']} "
                  f"{school['學校名稱']}", file=sys.stderr)

    results.sort(key=lambda pair: pair[0]["school_code"])
    coverage = [pair[0] for pair in results]
    candidates = sorted(
        (row for _, rows in results for row in rows),
        key=lambda row: (row["school_code"], row["document_url"]),
    )
    write_rows(args.coverage, COVERAGE_COLUMNS, coverage)
    write_rows(args.candidates, CANDIDATE_COLUMNS, candidates)
    summarize(coverage, candidates, args)


def summarize(coverage, candidates, args):
    counts = {
        "schools": len(coverage),
        "reachable": sum(row["reachable"] for row in coverage),
        "NSS sites": sum(row["discovery"] == "nss" for row in coverage),
        "sitemap fallbacks": sum(
            row["discovery"] == "sitemap" for row in coverage
        ),
        "schools with candidates": sum(
            row["candidate_documents"] > 0 for row in coverage
        ),
        "candidate documents": len(candidates),
    }
    print("\n" + "\n".join(f"{label}: {value}" for label, value in counts.items()),
          file=sys.stderr)
    print(f"coverage: {args.coverage}\ncandidates: {args.candidates}",
          file=sys.stderr)


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory-url", default=DIRECTORY_URL)
    parser.add_argument("--coverage", default=data_path(
        "high-school-entry-report-coverage.tsv"
    ))
    parser.add_argument("--candidates", default=data_path(
        "high-school-entry-report-candidates.tsv"
    ))
    parser.add_argument("--school-code", action="append", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--max-results", type=int, default=200)
    parser.add_argument("--keywords", nargs="+", default=list(KEYWORDS))
    args = parser.parse_args(argv)
    if (args.workers < 1 or args.timeout <= 0 or args.max_results < 1 or
            not args.keywords):
        parser.error("workers, timeout, and max-results must be positive")
    return args


if __name__ == "__main__":
    run(arguments())
