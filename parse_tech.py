"""Parse 四技二專聯合登記分發 minimum-admission-score PDFs into a TSV.

The 統測 counts 國文/英文/數學/專業(一)/專業(二), each out of 100, so a 系科組's
maximum is 100 * sum(weights) and `norm` is built exactly as in parse_uac.py.

A department recruits from several 群(類)別 with different weight combinations,
so it appears on several rows; ranking aggregates them by admitted headcount.
"""

import glob
import os
import re
import sys

from parse_uac import pdf_text

MAX_PER_SUBJECT = 100.0
ROW = re.compile(
    r"(\d{5})\s+"  # 志願代碼
    r"([A-Z]\d+)\s+"  # 權重組別
    r"(\S+?)\s\s+"  # 學校名稱
    r"(\S+?)\s\s+"  # 系科組學程名稱
    r"((?:\S+\*\d+\.\d+\s*\+?\s*)+)\s+"  # 各科目加權
    r"(\d+)\s+"  # 招生名額
    r"(\d+)\s+"  # 錄取人數
    r"([\d.]+)"  # 錄取總分數
)


def full_school(school, following):
    """Private schools wrap as 長庚學校財團法人 / 長庚科技大學 across two lines."""
    if not school.endswith("財團法人"):
        return school
    for line in following:
        parts = line.split()
        if len(parts) == 1 and parts[0].endswith(("大學", "學院", "專科學校")):
            return parts[0]
        if parts:
            break
    return school


def parse(pdf, year):
    rows = []
    lines = pdf_text(pdf).splitlines()
    for i, line in enumerate(lines):
        m = ROW.search(line)
        if not m:
            continue
        code, group, school, dept, weights, quota, admitted, score = m.groups()
        school = full_school(school, lines[i + 1 : i + 4])
        total_weight = sum(float(w) for w in re.findall(r"\*(\d+\.\d+)", weights))
        if not total_weight or not int(admitted):
            continue
        rows.append(
            {
                "year": year,
                "code": code,
                "school": school,
                "dept": dept,
                "weight_group": group,
                "total_weight": round(total_weight, 2),
                "seats": int(admitted),
                "cutoff": float(score),
                "norm": round(float(score) / (MAX_PER_SUBJECT * total_weight), 4),
            }
        )
    return rows


def main(out_path):
    rows = []
    for pdf in sorted(glob.glob(os.path.join(os.path.dirname(__file__), "tech", "union42-*.pdf"))):
        year = re.search(r"union42-(\d+)-", pdf).group(1)
        got = parse(pdf, year)
        print(f"{year}: {len(got)} 系科組", file=sys.stderr)
        rows.extend(got)
    cols = list(rows[0])
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r[c]) for c in cols) + "\n")
    print(f"wrote {len(rows)} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(os.path.join(os.path.dirname(__file__), "tech-cutoffs.tsv"))
