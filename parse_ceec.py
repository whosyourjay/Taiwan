"""Parse 大考中心 subject score distributions into a TSV of score counts.

Two layouts, one per era:

  108-110  各科成績人數累計表 — 指考, raw marks binned to 100 points, each subject
           its own sheet block, scores split across two side-by-side halves.
  111-114  各科級分人數百分比累計表 — 分科測驗, and the companion
           學測使用於分發入學 table, both already on the 60-point 級分 scale the
           分發入學 formulas count.

Output columns: year exam subject score seats, where `seats` is the number of
candidates scoring in that bin.
"""

import glob
import os
import re
import sys

HERE = os.path.dirname(__file__)
GRADES = "ceec/zhikao/*各科級分人數百分比累計表*.xls"
MARKS = "ceec/zhikao/*各科成績人數累計表*.xls"
YEARS = range(108, 115)


def cell(row, i):
    return str(row[i]).strip() if i < len(row) else ""


def number(text):
    text = text.replace(",", "").replace("%", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def read_grades(sheet):
    """級分 layout: a 級分 header row names the subjects, six columns each."""
    subjects = {}
    for r in range(sheet.nrows):
        row = sheet.row_values(r)
        if cell(row, 0) == "級分":
            subjects = {i: cell(row, i) for i in range(1, len(row)) if cell(row, i)}
            continue
        score = number(cell(row, 0))
        if score is None or not subjects:
            continue
        for base, name in subjects.items():
            count = number(cell(row, base))
            if count is not None:
                yield name, score, count


def mark_midpoint(text):
    """Representative score for a 指考 one-point score band."""
    m = re.match(r"^(\d+(?:\.\d+)?)(?:\s*-\s*(\d+(?:\.\d+)?))?", text)
    if not m:
        return None
    low = float(m.group(1))
    high = float(m.group(2)) if m.group(2) else low
    return (low + high) / 2


def read_marks(sheet):
    """指考 layout: subject named alone on a row, scores in two side-by-side halves.

    CEEC groups raw marks into bands such as 49.00--49.99.  The midpoint is a
    less biased representative of that bin than its lower endpoint.
    """
    subject = None
    for r in range(sheet.nrows):
        row = sheet.row_values(r)
        if cell(row, 0) and not cell(row, 1) and number(cell(row, 0)) is None:
            subject = cell(row, 0)
            continue
        if not subject:
            continue
        for base in (0, 7):
            score = mark_midpoint(cell(row, base))
            count = number(cell(row, base + 1))
            if score is not None and count is not None:
                yield subject, score, count


def exam_of(path):
    return "xuece" if "學測使用於分發入學" in os.path.basename(path) else "zhikao"


def parse(path):
    import xlrd

    year = re.match(r"(\d+)", os.path.basename(path)).group(1)
    if int(year) not in YEARS:
        return []
    sheet = xlrd.open_workbook(path).sheet_by_index(0)
    reader = read_grades if "級分" in os.path.basename(path) else read_marks
    exam = exam_of(path)
    return [(year, exam, s, score, n) for s, score, n in reader(sheet) if n]


def main(out_path):
    rows = []
    for pattern in (GRADES, MARKS):
        for path in sorted(glob.glob(os.path.join(HERE, pattern))):
            got = parse(path)
            if got:
                subs = len({r[2] for r in got})
                print(f"{os.path.basename(path)[:44]:<46} {len(got):>5} rows, {subs} subjects",
                      file=sys.stderr)
                rows.extend(got)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("year\texam\tsubject\tscore\tseats\n")
        for row in rows:
            f.write("\t".join(str(x) for x in row) + "\n")
    print(f"wrote {len(rows)} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(os.path.join(HERE, "ceec-scores.tsv"))
