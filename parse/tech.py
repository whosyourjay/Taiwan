"""Parse 四技二專聯合登記分發 minimum-admission-score PDFs into a TSV.

The 統測 counts 國文/英文/數學/專業(一)/專業(二), each out of 100, so a 系科組's
maximum is 100 * sum(weights) and `norm` is built exactly as in `parse.uac`.

A department recruits from several 群(類)別 with different weight combinations,
so it appears on several rows; ranking aggregates them by admitted headcount.
"""

import glob
import re
import sys

from lib import tsvio
from lib.paths import data_path, source_path
from parse.uac import pdf_text

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
# Every row is filed under its 群(類), printed at the head of the line. Which
# 專業科目 papers a cutoff was scored on follows from it.
GROUP = re.compile(r"^\s*\d{2}(\S+[群類])")
WEIGHT = re.compile(r"(\S+?)\*(\d+\.\d+)")

# Through 107 every program used the same 700-point formula, and the report
# printed the lowest total and professional subtotal instead of repeating the
# formula on every row. The short group labels are expanded to the names used by
# TCTE's score-distribution tables.
LEGACY_GROUPS = {
    "01機械": "機械群", "02動機": "動力機械群",
    "03電機": "電機與電子群電機類", "04資電": "電機與電子群資電類",
    "05化工": "化工群", "06土木": "土木與建築群", "07設計": "設計群",
    "08工管": "工程與管理類", "09商管": "商業與管理群",
    "10衛護": "衛生與護理類", "11食品": "食品群",
    "12幼保": "家政群幼保類", "13生活": "家政群生活應用類",
    "14農業": "農業群", "15英語": "外語群英語類",
    "16日語": "外語群日語類", "17餐旅": "餐旅群", "18海事": "海事群",
    "19水產": "水產群", "20藝影": "藝術群影視類",
}
LEGACY_WEIGHTS = (
    ("國文", "1.00"), ("英文", "1.00"), ("數學", "1.00"),
    ("專業(一)", "2.00"), ("專業(二)", "2.00"),
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


def parse_legacy(text, year):
    """Read the fixed-weight layout used through 107."""
    rows = []
    total_weight = sum(float(weight) for _, weight in LEGACY_WEIGHTS)
    for line in text.splitlines():
        fields = line.split()
        if len(fields) != 10 or fields[0] not in LEGACY_GROUPS:
            continue
        group, code, school, dept, _, admitted, _, _, cutoff, _ = fields
        if not admitted.isdigit() or not int(admitted) or cutoff == "--":
            continue
        score = float(cutoff)
        rows.append({
            "year": year,
            "code": code,
            "school": school,
            "dept": dept,
            "group": LEGACY_GROUPS[group],
            "subjects": " ".join(f"{s}x{w}" for s, w in LEGACY_WEIGHTS),
            "weight_group": "fixed",
            "total_weight": total_weight,
            "seats": int(admitted),
            "cutoff": score,
            "norm": round(score / (MAX_PER_SUBJECT * total_weight), 4),
        })
    return rows


def parse(pdf, year):
    body = pdf_text(pdf)
    if int(year) <= 107:
        return parse_legacy(body, year)
    rows = []
    lines = body.splitlines()
    subject_group = ""
    for i, line in enumerate(lines):
        m = ROW.search(line)
        head = GROUP.match(line[: m.start()] if m else line)
        if head:
            subject_group = head.group(1)
        if not m:
            continue
        code, group, school, dept, weights, quota, admitted, score = m.groups()
        school = full_school(school, lines[i + 1 : i + 4])
        pairs = WEIGHT.findall(weights)
        total_weight = sum(float(w) for _, w in pairs)
        if not total_weight or not int(admitted):
            continue
        rows.append(
            {
                "year": year,
                "code": code,
                "school": school,
                "dept": dept,
                "group": subject_group,
                "subjects": " ".join(f"{s}x{w}" for s, w in pairs),
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
    pattern = source_path("tech", "union42-*.pdf")
    for pdf in sorted(glob.glob(pattern)):
        year = re.search(r"union42-(\d+)-", pdf).group(1)
        got = parse(pdf, year)
        print(f"{year}: {len(got)} 系科組", file=sys.stderr)
        rows.extend(got)
    written = tsvio.write_rows(out_path, rows)
    print(f"wrote {written} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(data_path("tech-cutoffs.tsv"))
