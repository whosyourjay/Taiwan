"""Extract and classify high-school entry-report candidates automatically."""

import argparse
import concurrent.futures
import os
import re
import subprocess
import sys
import unicodedata

from fetch.high_school_entry_audit import clean_field, write_rows
from fetch.high_school_entry_documents import MANIFEST, OUTDIR, filename
from lib import tsvio
from lib.paths import data_path


INPUT = data_path("high-school-entry-report-candidates.tsv")
OUTPUT = data_path("high-school-entry-report-classification.tsv")
PLAN = data_path("high-school-entry-report-download-plan.tsv")
OUTPUT_COLUMNS = (
    "year",
    "school_code",
    "high_school",
    "city",
    "document_name",
    "document_url",
    "classification",
    "confidence",
    "classification_method",
    "evidence",
    "download_status",
    "bytes",
    "sha256",
    "text_chars",
    "extraction_error",
    "local_path",
)

CAP_BINS = {
    "5A": r"(?<![A-Z0-9])5\s*A(?![A-Z0-9])",
    "4A1B": r"(?<![A-Z0-9])4\s*A\s*1\s*B(?![A-Z0-9])",
    "3A2B": r"(?<![A-Z0-9])3\s*A\s*2\s*B(?![A-Z0-9])",
    "2A3B": r"(?<![A-Z0-9])2\s*A\s*3\s*B(?![A-Z0-9])",
    "1A4B": r"(?<![A-Z0-9])1\s*A\s*4\s*B(?![A-Z0-9])",
    "5B": r"(?<![A-Z0-9])5\s*B(?![A-Z0-9])",
}
ENTRANCE = re.compile(
    r"新生入學情形|新生.{0,20}(?:會考|基測|入學成績)|"
    r"入學學生.{0,20}(?:會考|基測|成績)|(?:會考|基測).{0,20}新生|"
    r"國中基本學力測驗.{0,20}(?:成績|新生)|入學成績"
)
REPORT = re.compile(
    r"高中優質化.{0,30}(?:成果|成效|考核)|優質高中認證|學校經營計畫|"
    r"(?:學校|校務).{0,10}中長程|中長程教育發展計畫|校務發展計畫|"
    r"校務評鑑|自我評鑑"
)
TRAINING = re.compile(r"研習|工作坊|講座|研討會|教師增能|來函|活動計畫")
ADMISSION = re.compile(r"招生簡章|招生辦法|新生報到|錄取名單|轉學考|招生訊息")
RANGE = re.compile(
    r"(?<!\d)(\d{1,3}(?:\.\d+)?)\s*(?:[-~～－至])\s*"
    r"(\d{1,3}(?:\.\d+)?)(?!\d)"
)
QUANTILE = re.compile(r"(?<![A-Z])P\s*(5|10|25|50|75|90|95)(?!\d)", re.I)
PR_VALUE = re.compile(r"PR\s*(\d{1,3})(?!\d)", re.I)
STAT_TERMS = ("最高", "最低", "平均", "中位數", "前25%", "後25%")
EXAM_SCORE = re.compile(r"會考|基測|基本學力測驗|入學成績|成績分[布佈]")
KEEP_CLASSIFICATIONS = {
    "entrance_distribution",
    "possible_entrance_distribution",
    "entrance_report_no_distribution",
    "needs_ocr_or_conversion",
}


# Below this an extraction has produced too little to judge on its content.
MIN_CONTENT = 40


def normalized(text):
    text = unicodedata.normalize("NFKC", text or "")
    return re.sub(r"\s+", " ", text).strip()


def extract_pdf(path, timeout):
    result = subprocess.run(
        ["pdftotext", "-layout", path, "-"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout.decode("utf-8", "replace")


def extract_office(path, timeout):
    result = subprocess.run(
        ["/usr/bin/textutil", "-convert", "txt", "-stdout", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        raise ValueError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout.decode("utf-8", "replace")


def extract_xls(path):
    import xlrd
    book = xlrd.open_workbook(path, on_demand=True)
    lines = []
    for sheet in book.sheets():
        lines.append(sheet.name)
        for row in range(sheet.nrows):
            lines.append("\t".join(str(sheet.cell_value(row, col))
                                   for col in range(sheet.ncols)))
    book.release_resources()
    return "\n".join(lines)


def extract(path, timeout):
    suffix = os.path.splitext(path)[1].lower()
    if suffix == ".pdf":
        return extract_pdf(path, timeout)
    if suffix in {".doc", ".docx", ".odt"}:
        return extract_office(path, timeout)
    if suffix in {".xls", ".xlsx"}:
        return extract_xls(path)
    raise ValueError(f"unsupported document type {suffix}")


def signals(text):
    cap = [name for name, pattern in CAP_BINS.items()
           if re.search(pattern, text, re.I)]
    quantiles = sorted(set(QUANTILE.findall(text)))
    prs = sorted(set(PR_VALUE.findall(text)))
    stats = [term for term in STAT_TERMS if term in text]
    ranges = RANGE.findall(text)
    return cap, quantiles, prs, stats, ranges


def evidence_of(cap, quantiles, prs, stats, ranges, entrance, report):
    parts = []
    if entrance:
        parts.append("entrance_context")
    if report:
        parts.append("school_report")
    if cap:
        parts.append("cap_bins=" + ",".join(cap))
    if quantiles:
        parts.append("percentiles=P" + ",P".join(quantiles))
    if prs:
        parts.append("pr_values=" + ",".join(prs[:8]))
    if stats:
        parts.append("stats=" + ",".join(stats))
    if ranges:
        parts.append(f"score_ranges={len(ranges)}")
    return ";".join(parts)


def classify(content, metadata="", extraction_error=""):
    content = normalized(content)
    metadata = normalized(metadata)
    combined = metadata + " " + content
    entrance = bool(ENTRANCE.search(combined))
    report = bool(REPORT.search(combined))
    exam_score = bool(EXAM_SCORE.search(combined))
    cap, quantiles, prs, stats, ranges = signals(combined)
    evidence = evidence_of(
        cap, quantiles, prs, stats, ranges, entrance, report
    )
    if exam_score:
        evidence = ";".join(filter(None, (evidence, "exam_score_context")))
    structured = len(cap) >= 2 or len(quantiles) >= 2 or len(prs) >= 2
    numeric = exam_score and (len(stats) >= 2 or len(ranges) >= 2)

    if extraction_error or len(content) < MIN_CONTENT:
        if entrance or report:
            return "needs_ocr_or_conversion", "medium", evidence
        # Short text that still names what it is has been read, just briefly.
        if not (ADMISSION.search(combined) or TRAINING.search(combined)):
            return "unreadable", "high", evidence
    if entrance and (structured or numeric):
        return "entrance_distribution", "high", evidence
    if report and structured:
        return "possible_entrance_distribution", "medium", evidence
    if entrance:
        return "entrance_report_no_distribution", "high", evidence
    if report:
        return "school_plan_or_report", "high", evidence
    if ADMISSION.search(combined):
        return "admissions_notice", "high", evidence
    if TRAINING.search(combined):
        return "training_or_event", "high", evidence
    return "other", "medium", evidence


def metadata_classification(candidate):
    title = normalized(candidate.get("page_title", ""))
    name = normalized(candidate.get("document_name", ""))
    metadata = title + " " + name
    entrance = bool(ENTRANCE.search(metadata))
    report = bool(REPORT.search(metadata))
    cap, quantiles, prs, stats, ranges = signals(metadata)
    evidence = evidence_of(
        cap, quantiles, prs, stats, ranges, entrance, report
    )
    if entrance or report or any((cap, quantiles, prs, stats, ranges)):
        return "needs_content", "", evidence
    if ADMISSION.search(metadata):
        return "admissions_notice", "high", evidence
    if TRAINING.search(metadata):
        return "training_or_event", "high", evidence
    stem = os.path.splitext(name)[0]
    if not title and len(re.findall(r"[一-鿿]", stem)) < 3:
        return "needs_content", "", evidence
    return "other", "medium", evidence


def output_row(candidate, manifest, label, confidence, method, evidence,
               text="", error="", path=""):
    return {
        "year": candidate["year"],
        "school_code": candidate["school_code"],
        "high_school": candidate["high_school"],
        "city": candidate["city"],
        "document_name": candidate["document_name"],
        "document_url": candidate["document_url"],
        "classification": label,
        "confidence": confidence,
        "classification_method": method,
        "evidence": evidence,
        "download_status": manifest.get("status", "not_needed"),
        "bytes": manifest.get("bytes", 0),
        "sha256": manifest.get("sha256", ""),
        "text_chars": len(normalized(text)),
        "extraction_error": clean_field(error),
        "local_path": os.path.relpath(path) if path else "",
    }


def classify_row(candidate, manifest, args, previous=None):
    metadata_label, metadata_confidence, metadata_evidence = (
        metadata_classification(candidate)
    )
    if not manifest:
        label = ("not_downloaded" if metadata_label == "needs_content"
                 else metadata_label)
        confidence = ("high" if label == "not_downloaded"
                      else metadata_confidence)
        return output_row(
            candidate, {}, label, confidence, "metadata", metadata_evidence
        )
    status = manifest.get("status", "missing")
    filename = manifest.get("filename", "")
    path = os.path.join(args.source_dir, filename) if filename else ""
    if previous and status in {"ok", "cached"} and not os.path.exists(path):
        previous = dict(previous)
        previous["download_status"] = "pruned"
        previous["local_path"] = ""
        return previous
    metadata = " ".join((candidate.get("page_title", ""),
                         candidate.get("document_name", "")))
    text, error = "", ""
    if status in {"ok", "cached"} and os.path.exists(path):
        try:
            text = extract(path, args.extract_timeout)
        except Exception as exc:
            error = str(exc)
    else:
        error = manifest.get("error", "document not downloaded")
    label, confidence, evidence = classify(text, metadata, error)
    if status not in {"ok", "cached"}:
        label, confidence = "download_failed", "high"
    return output_row(
        candidate, manifest, label, confidence, "content", evidence,
        text, error, path,
    )


def write_plan(args):
    candidates = list(tsvio.read_rows(args.input))
    rows = [row for row in candidates
            if metadata_classification(row)[0] == "needs_content"]
    write_rows(args.plan, list(candidates[0]), rows)
    print(f"{len(rows)}/{len(candidates)} documents need content",
          file=sys.stderr)
    print(f"wrote {args.plan}", file=sys.stderr)


def prune_cache(rows, candidates, source_dir):
    keep = {os.path.basename(row["local_path"]) for row in rows
            if row["classification"] in KEEP_CLASSIFICATIONS
            and row["local_path"]}
    possible = {filename(row["document_url"]) for row in candidates}
    removed_files = removed_bytes = 0
    for name in possible - keep:
        path = os.path.join(source_dir, name)
        if not os.path.isfile(path):
            continue
        removed_bytes += os.path.getsize(path)
        os.remove(path)
        removed_files += 1
    print(f"pruned {removed_files} files ({removed_bytes:,} bytes)",
          file=sys.stderr)


def run(args):
    candidates = list(tsvio.read_rows(args.input))
    if args.plan_only:
        write_plan(args)
        return
    manifests = {row["document_url"]: row
                 for row in tsvio.read_rows(args.manifest)}
    previous = {}
    if os.path.exists(args.output):
        previous = {row["document_url"]: row
                    for row in tsvio.read_rows(args.output)}
    rows = []
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.workers) as executor:
        futures = [executor.submit(
            classify_row, row, manifests.get(row["document_url"], {}), args,
            previous.get(row["document_url"]),
        ) for row in candidates]
        for done, future in enumerate(
                concurrent.futures.as_completed(futures), 1):
            rows.append(future.result())
            if done % 50 == 0 or done == len(futures):
                print(f"{done:>4}/{len(futures)} classified", file=sys.stderr)
    rows.sort(key=lambda row: (row["school_code"], row["document_url"]))
    write_rows(args.output, OUTPUT_COLUMNS, rows)
    summary = {}
    for row in rows:
        summary[row["classification"]] = summary.get(
            row["classification"], 0
        ) + 1
    for label, count in sorted(summary.items(), key=lambda item: -item[1]):
        print(f"{count:>4}  {label}", file=sys.stderr)
    print(f"wrote {len(rows)} rows to {args.output}", file=sys.stderr)
    if args.prune:
        prune_cache(rows, candidates, args.source_dir)


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=INPUT)
    parser.add_argument("--manifest", default=MANIFEST)
    parser.add_argument("--source-dir", default=OUTDIR)
    parser.add_argument("--output", default=OUTPUT)
    parser.add_argument("--plan", default=PLAN)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--prune", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--extract-timeout", type=float, default=60)
    args = parser.parse_args(argv)
    if args.workers < 1 or args.extract_timeout <= 0:
        parser.error("workers and extract-timeout must be positive")
    return args


if __name__ == "__main__":
    run(arguments())
