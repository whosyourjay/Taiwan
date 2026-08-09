"""Parse 大考中心 subject score distributions into a TSV of score counts.

Three layouts, on two different scales:

  108-110  各科成績人數累計表 — 指考, raw marks binned to 100 points, each subject
           its own sheet block, scores split across two side-by-side halves.
  111-114  各科級分人數百分比累計表 — 分科測驗, and the companion
           學測使用於分發入學 table, both already on the 60-point 級分 scale the
           分發入學 formulas count.
  100-114  各科級分人數分布表 — 學測 on its own 0-15 級分 scale, counted over
           everyone who sat the exam rather than the 分發入學 entrants alone.
           繁星 and 個人申請 quote this scale, so it is a separate `exam`.

The 學測 set also publishes 2至4科不同科目組合級分人數分布表, the observed
distribution of every multi-subject total. Reading a 國英數自 sum off that table
needs no assumption about how the subjects correlate, unlike inferring one
subject at a time. Those totals arrive as subjects named `國文、英文、數學、自然`.

Output columns: year exam subject score seats, where `seats` is the number of
candidates scoring in that bin.
"""

import glob
import os
import re
import sys

from lib.paths import data_path, path as repo_path

GRADES = "ceec/zhikao/*各科級分人數百分比累計表*.xls"
MARKS = "ceec/zhikao/*各科成績人數累計表*.xls"
# CEEC renamed these mid-series (分布表 -> 百分比累計表) and some years ship the
# same table twice, once cumulated downwards. Only the 分布表 spelling is taken
# for now, which covers 108-112; widening it needs deduplication first.
GSAT = "ceec/xuece/*各科級分人數分布表*.xls"
GSAT_COMBO = "ceec/xuece/*2至4科不同科目組合級分人數分布表*.xls"
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
    """Which exam, and on which scale, a statistics file reports.

    `xuece` is 學測 rescaled to the 60 points 分發入學 counts; `gsat` is the same
    exam on its native 0-15 級分 scale over the whole cohort. They are different
    denominators over different populations, so they stay separate.
    """
    name = os.path.basename(path)
    if "學測使用於分發入學" in name:
        return "xuece"
    if f"{os.sep}xuece{os.sep}" in path:
        return "gsat"
    return "zhikao"


def parse(path):
    import xlrd

    year = re.match(r"(\d+)", os.path.basename(path)).group(1)
    if int(year) not in YEARS:
        return []
    # The 學測 combination tables split 2科/3科/4科 across sheets; every other
    # workbook holds one.
    book = xlrd.open_workbook(path)
    reader = read_grades if "級分" in os.path.basename(path) else read_marks
    exam = exam_of(path)
    return [(year, exam, s, score, n)
            for sheet in book.sheets()
            for s, score, n in reader(sheet) if n]


def main(out_path):
    rows = []
    for pattern in (GRADES, MARKS, GSAT, GSAT_COMBO):
        for source in sorted(glob.glob(repo_path(pattern))):
            got = parse(source)
            if got:
                subs = len({r[2] for r in got})
                print(f"{os.path.basename(source)[:44]:<46} {len(got):>5} rows, "
                      f"{subs} subjects",
                      file=sys.stderr)
                rows.extend(got)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("year\texam\tsubject\tscore\tseats\n")
        for row in rows:
            f.write("\t".join(str(x) for x in row) + "\n")
    print(f"wrote {len(rows)} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(data_path("ceec-scores.tsv"))
