"""Parse UAC 分發入學 minimum-admission-score PDFs into a TSV.

One row per 系組 (department/group) per year, with the weighted cutoff score
normalised to a 0-1 fraction of the maximum attainable weighted score.

Since 111 學年度 every subject is reported on a 60-point scale (學測 級分 are
multiplied by 4), so a department's maximum is 60 * sum(weights).
"""

import glob
import os
import re
import subprocess
import sys

# 指考 (through 110) scored each subject out of 100; 分科測驗 (111 on) uses 60 級分,
# with 學測 級分 scaled by 4 onto the same 60-point range.
def max_per_subject(year):
    return 100.0 if int(year) <= 110 else 60.0


# 術科考試 is run by its own committee on its own 100-point scale, which the
# 指考 -> 分科測驗 switch left alone. Least squares over the departments that
# admit both with and without it puts that maximum at 100.
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
    txt = pdf.replace(".pdf", ".txt")
    if not os.path.exists(txt):
        subprocess.run(["pdftotext", "-layout", pdf, txt], check=True)
    with open(txt, encoding="utf-8", errors="replace") as f:
        return f.read()


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


def main(out_path):
    rows = []
    for pdf in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "uac-*-cutoffs.pdf"))):
        year = re.search(r"uac-(\d+)-", pdf).group(1)
        got = parse(pdf, year)
        print(f"{year}: {len(got)} 系組", file=sys.stderr)
        rows.extend(got)
    cols = list(rows[0])
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c]) for c in cols) + "\n")
    print(f"wrote {len(rows)} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(os.path.join(os.path.dirname(__file__), "uac-cutoffs.tsv"))
