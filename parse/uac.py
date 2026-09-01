"""Parse UAC 分發入學 minimum-admission-score PDFs into a TSV.

One row per 系組 (department/group) per year, with the weighted cutoff score
normalised to a 0-1 fraction of the maximum attainable weighted score. The UAC
guide assigns 60 levels to 學測 and 分科採計 scores from 111, and keeps 術科 on
its 100-point scale.
"""

import glob
import gzip
import os
import re
import subprocess
import sys

from lib import tsvio
from lib.paths import data_path, path, source_path

# 指考 (through 110) uses 100 points; UAC academic scores from 111 use 60 levels.
def max_per_subject(year):
    return 100.0 if int(year) <= 110 else 60.0


# UAC's admissions guide specifies a 100-point scale for 術科採計.
ART_MAX = 100.0


def max_score(year, subjects):
    """Highest weighted total attainable under one department's formula."""
    academic = max_per_subject(year)
    return sum((ART_MAX if "術" in s else academic) * float(w) for s, w in subjects)


WEIGHT = re.compile(r"([一-鿿][A-Za-z一-鿿]*)x(\d+\.\d+)")
# The 採計及加權 block is the only reliable anchor: 系組名 may run long enough to
# swallow its column separator, or wrap onto a line of its own.
BLOCK = re.compile(r"((?:[一-鿿][A-Za-z一-鿿]*x\d+\.\d+\s+)+)(\d+)\s+([\d.]+|-+)(?:\s|$)")
PREFIX = re.compile(r"^\s*(\d{4})\s+(.*)$")


SCHOOL_END = re.compile(r"^(.*?(?:大學|學院|專科學校))\s*(.+)$")


def split_prefix(prefix, carry):
    """Split the text before the weight block into (校名, 系組名)."""
    parts = [p for p in re.split(r"\s{2,}", prefix.strip()) if p]
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    if len(parts) == 1:
        # Columns collided into one field: 校名 ends at 大學/學院/專科學校.
        m = SCHOOL_END.match(parts[0])
        if m:
            return m.group(1), m.group(2)
        # Otherwise 系組名 wrapped to its own line above; `carry` holds it.
        return parts[0], carry
    return "", carry


def pdf_text(pdf):
    txt = os.path.splitext(pdf)[0] + ".txt"
    compressed = txt + ".gz"
    plain_is_newer = (os.path.exists(txt) and
                      (not os.path.exists(compressed) or
                       os.path.getmtime(txt) > os.path.getmtime(compressed)))
    if plain_is_newer:
        with open(txt, encoding="utf-8", errors="replace") as f:
            return f.read()
    if os.path.exists(compressed):
        with gzip.open(compressed, "rt", encoding="utf-8", errors="replace") as f:
            return f.read()
    result = subprocess.run(
        ["pdftotext", "-layout", pdf, "-"], check=True,
        stdout=subprocess.PIPE,
    )
    temporary = compressed + ".part"
    with gzip.open(temporary, "wb") as handle:
        handle.write(result.stdout)
    os.replace(temporary, compressed)
    return result.stdout.decode("utf-8", "replace")


def parse(pdf, year):
    rows, carry = [], ""
    for line in pdf_text(pdf).splitlines():
        block = BLOCK.search(line)
        head = PREFIX.match(line)
        if not block or not head:
            # A bare fragment is a 系組名 that wrapped; remember it for the next row.
            stripped = line.strip()
            if stripped and not block and "學年度" not in stripped:
                carry = stripped
            continue
        code = head.group(1)
        prefix = line[head.start(2) : block.start(1)]
        school, dept = split_prefix(prefix, carry)
        carry = ""
        weights, seats, score = block.group(1), block.group(2), block.group(3)
        subjects = WEIGHT.findall(weights)
        if not subjects:
            continue
        total_weight = sum(float(w) for _, w in subjects)
        if score.startswith("-") or total_weight == 0:
            continue
        cutoff = float(score)
        rows.append(
            {
                "year": year,
                "code": code,
                "school": school,
                "dept": dept,
                "subjects": " ".join(f"{s}x{w}" for s, w in subjects),
                "n_subjects": len(subjects),
                "total_weight": round(total_weight, 2),
                "seats": int(seats),
                "cutoff": cutoff,
                "norm": round(cutoff / max_score(year, subjects), 4),
            }
        )
    return rows


def official_names(source=None):
    """Program names keyed by year and code from UAC's annual workbooks."""
    source = source or data_path("uac-seats.tsv")
    if not os.path.exists(source):
        return {}
    return {(row["year"], row["code"]): (row["school"], row["dept"])
            for row in tsvio.read_rows(source)}


def repair_names(rows, names):
    """Replace abbreviated PDF labels with the workbook's official labels."""
    repaired = 0
    for row in rows:
        name = names.get((row["year"], row["code"]))
        if name and (row["school"], row["dept"]) != name:
            row["school"], row["dept"] = name
            repaired += 1
    return repaired


def main(out_path):
    rows, names = [], official_names()
    for pdf in sorted(glob.glob(source_path("uac", "*-cutoffs.pdf"))):
        year = os.path.basename(pdf).split("-")[0]
        got = parse(pdf, year)
        repaired = repair_names(got, names)
        print(f"{year}: {len(got)} 系組, {repaired} names expanded", file=sys.stderr)
        rows.extend(got)
    written = tsvio.write_rows(out_path, rows)
    print(f"wrote {written} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(data_path("uac-cutoffs.tsv"))
