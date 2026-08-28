"""Parse 繁星推薦 錄取標準 PDFs in star/ into a TSV, one row per 校系.

繁星 ranks applicants by 比序項目 in a fixed order, starting with 在校學業成績
全校排名百分比 — where the applicant sits in their own high school. The standard
printed against that item is the marginal admittee's percentile, so `gpa_r1` is
the difficulty number: 1% is harder than 17%. Later items only break ties among
applicants level on the earlier ones.

第八類學群 (medicine) reports 通過篩選 rather than 錄取: those rows are a
screening threshold ahead of a 甄試, so their counts run to twice the quota.

The tables are laid out in fixed columns, so words are assigned to a column by
horizontal position against the header row's anchors.
"""

import csv
import glob
import io
import os
import re
import subprocess
import sys

from lib import tsvio
from lib.paths import data_path, path, source_path

# 檢定 subject column, then the 比序 item and its four value columns.
GATE_SUBJECTS = ("國文", "英文", "數學", "數學A", "數學B", "社會", "自然", "英聽")
BAND = re.compile(r"^(頂標|前標|均標|後標|底標)$")
LEVEL = re.compile(r"^(\d+)級分$")
PERCENT = re.compile(r"^([\d.]+)%[＊*]?$")
DEPT_CODE = re.compile(r"^\d{5}$")
COLLEGE = re.compile(r"\((\d{3})\)(.+)")


def pages_of(path):
    """Poppler word boxes grouped by page.

    ``pdftotext`` reads this corpus much faster than constructing pdfminer's
    full page layout, while retaining the coordinates the fixed-column parser
    needs.
    """
    process = subprocess.run(
        ["pdftotext", "-tsv", path, "-"], capture_output=True, text=True,
        check=True,
    )
    pages = {}
    for row in csv.DictReader(io.StringIO(process.stdout), delimiter="\t"):
        if row["level"] != "5" or not row["text"].strip():
            continue
        left, width = float(row["left"]), float(row["width"])
        pages.setdefault(int(row["page_num"]), []).append({
            "text": row["text"], "x0": left, "x1": left + width,
            "top": float(row["top"]),
        })
    return [pages[number] for number in sorted(pages)]


def rows_of(words):
    """Page words grouped into visual rows, each sorted left to right."""
    buckets = {}
    for w in words:
        w["cx"] = (w["x0"] + w["x1"]) / 2
        buckets.setdefault(round(w["top"] / 3), []).append(w)
    return [sorted(buckets[k], key=lambda w: w["cx"]) for k in sorted(buckets)]


def anchors(rows):
    """Column centres for (比序項目, 第一輪人數, 標準, 第二輪人數, 標準).

    The header row carries 科目 ... 項目 ... 項目 followed by the four value
    headings, so their centres give the whole right-hand block in one pass.
    """
    for row in rows:
        texts = [w["text"] for w in row]
        if "科目" not in texts or texts.count("項目") < 2:
            continue
        i = len(texts) - 1 - texts[::-1].index("項目")
        if len(row) - i < 5:
            continue
        return [w["cx"] for w in row[i:i + 5]]
    return None


def college_of(rows):
    for row in rows:
        for w in row:
            m = COLLEGE.search(w["text"])
            if m and "校名" in w["text"]:
                return m.group(1), m.group(2).strip()
    return "", ""


def cell(row, x, tol=20):
    """Text of the word centred nearest x, or "" if none is within tol."""
    near = [w for w in row if abs(w["cx"] - x) <= tol]
    return min(near, key=lambda w: abs(w["cx"] - x))["text"] if near else ""


def left_of(row):
    """Words in the 校系代碼 / 校系名稱 / 名額 / 錄取人數 columns."""
    return [w["text"] for w in row if w["cx"] < 330]


def is_dept(row):
    left = left_of(row)
    return (len(left) >= 3 and DEPT_CODE.match(left[0])
            and left[-1].isdigit() and left[-2].isdigit())


def blocks(rows, item_x):
    """One block per 校系 on the page, starting at its 在校學業 row.

    在校學業 is the first 比序項目 for every 校系, so it marks the top of a
    block. Cutting there rather than midway between 校系代碼 rows keeps the
    rows a long 校系名稱 wraps onto, which make blocks uneven in height.
    """
    hdr = next((i for i, r in enumerate(rows)
                if any(w["text"] == "科目" for w in r)), -1)
    starts = [i for i in range(hdr + 1, len(rows))
              if cell(rows[i], item_x, tol=30) == "在校學業"]
    if not starts:
        return []
    stop = next((i for i in range(starts[0], len(rows))
                 if any("說明" in w["text"] or w["text"] == "Page" for w in rows[i])),
                len(rows))
    ends = starts[1:] + [stop]
    return [rows[a:b] for a, b in zip(starts, ends)]


def gates(block):
    """The 檢定標準 as `國文頂標13 英文前標12`, skipping unset subjects."""
    out = []
    for row in block:
        t = [w["text"] for w in row]
        for i, x in enumerate(t[:-2]):
            if x in GATE_SUBJECTS and BAND.match(t[i + 1]) and LEVEL.match(t[i + 2]):
                out.append(f"{x}{t[i + 1]}{LEVEL.match(t[i + 2]).group(1)}")
    return " ".join(out)


def value(text):
    """A 標準 cell as a number: `3%` -> 3.0, `14` -> 14.0, `--` -> None."""
    m = PERCENT.match(text)
    if m:
        return float(m.group(1))
    return float(text) if re.match(r"^\d+(\.\d+)?$", text) else None


def blend(gpa1, gpa2, n1, n2):
    """One percentile per 校系, weighting each round by the seats it filled.

    Round 2 reopens the leftover seats to schools that already used their
    round-1 recommendation, so its standard is not reliably the looser of
    the two and cannot just be dropped.
    """
    parts = [(g, int(n)) for g, n in ((gpa1, n1), (gpa2, n2))
             if g != "" and n.isdigit() and int(n) > 0]
    if not parts:
        return gpa1 if gpa1 != "" else gpa2
    return round(sum(g * n for g, n in parts) / sum(n for _, n in parts), 3)


def head(block):
    """(dept_code, dept, quota, admitted) from the row carrying the 校系代碼.

    A long 校系名稱 wraps onto the rows above and below, leaving the code row
    with only three fields; the fragments are the only other text that far left.
    """
    for row in block:
        if not is_dept(row):
            continue
        left = left_of(row)
        name = "".join(left[1:-2])
        if not name:
            name = "".join(t for r in block if r is not row for t in left_of(r))
        return left[0], name, left[-2], left[-1]
    return None


def read(block, ax):
    """Ordered [(item, r1_n, r1_std, r2_n, r2_std)] down the 比序 column."""
    out = []
    for row in block:
        item = cell(row, ax[0], tol=30)
        if item:
            out.append([item] + [cell(row, x) for x in ax[1:]])
    return out


def round_counts(block, ax):
    """Round counts, which old PDFs sometimes print on the department row."""
    for row in block:
        r1, r2 = cell(row, ax[1]), cell(row, ax[3])
        if r1.isdigit():
            return ["", r1, "", r2, ""]
    return ["", "", "", "", ""]


def record(block, ax):
    """One 校系 as a dict of columns, or None if the block holds no 校系代碼."""
    h = head(block)
    if not h:
        return None
    items = read(block, ax)
    by = {i[0]: i for i in items}
    gpa = by.get("在校學業", ["", "", "--", "", "--"])
    counts = round_counts(block, ax)
    ties = [f"{i[0]}={i[2]}" for i in items[1:] if value(i[2]) is not None]
    g1, g2 = (value(gpa[2]), value(gpa[4]))
    g1, g2 = ("" if g1 is None else g1, "" if g2 is None else g2)
    return {
        "dept_code": h[0], "dept": h[1], "quota": h[2], "admitted": h[3],
        "r1_n": counts[1], "r2_n": counts[3],
        "gpa_r1": g1, "gpa_r2": g2,
        "gpa": blend(g1, g2, counts[1], counts[3]),
        "tiebreak_r1": ";".join(ties),
        "gates": gates(block),
    }


def parse(path):
    year, code, group = os.path.basename(path)[:-4].split("-")
    out, college = [], ("", "")
    for words in pages_of(path):
        rows = rows_of(words)
        college = college if college[0] else college_of(rows)
        ax = anchors(rows)
        if not ax:
            continue
        for block in blocks(rows, ax[0]):
            r = record(block, ax)
            if r:
                out.append({"year": year, "group": group,
                            "college_code": code, "college": college[1], **r})
    return out


def main(out_path):
    rows = []
    for pdf in sorted(glob.glob(source_path("star", "*.pdf"))):
        got = parse(pdf)
        print(f"{os.path.basename(pdf)}: {len(got)} 校系", file=sys.stderr)
        rows.extend(got)
    written = tsvio.write_rows(out_path, rows)
    print(f"wrote {written} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(data_path("star-cutoffs.tsv"))
