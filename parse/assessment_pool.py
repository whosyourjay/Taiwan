"""Estimate the 110 academic-year distinct current candidates for comparison."""

import glob
import re
import sys

import xlrd

from lib import tsvio
from lib.paths import data_path, path, source_path
from parse.uac import pdf_text


YEAR = "2021"
TONGCE = "tech/tcte-110-work-report.pdf"
GSAT = "ceec/xuece/110-11_報名人數統計總表*"

def as_int(value):
    return int(float(str(value).replace(",", "")))


def xuece_counts(source):
    sheet = xlrd.open_workbook(source).sheet_by_index(0)
    rows = [[str(cell.value).strip() for cell in row] for row in sheet.get_rows()]
    header = next(i for i, row in enumerate(rows) if "合計" in row and "百分比" in row)
    total_col = rows[header].index("合計")
    rows = rows[header + 1:]
    values = {}
    for row in rows:
        if len(row) <= total_col or not row[1]:
            continue
        try:
            values[row[1]] = as_int(row[total_col])
        except ValueError:
            continue
    total = next(as_int(row[total_col]) for row in rows if row[0] == "合計")
    return {"total": total, "current": values["應屆"],
            "vocational": values["公立職業學校"] + values["私立職業學校"],
            "ordinary": values["公立普通高中"] + values["私立普通高中"]}

def tongce_counts(source):
    text = pdf_text(source)
    first = text[text.rindex("表一、四技二專統一入學測驗歷年應屆"):]
    first = first[:first.index("表二、四技二專統一入學測驗歷年來源")]
    second = text[text.rindex("表二、四技二專統一入學測驗歷年來源"):]
    second = second[:second.index("表三、四技二專各考區")]
    candidates = re.search(
        r"^\s*110\s+([\d,]+)\s+[\d.]+%?\s+([\d,]+)\s+[\d.]+%\s+([\d,]+)(?:\s|$)",
        first, re.M)
    origins = re.search(
        r"^\s*110\s+([\d,]+)\s+[\d.]+%\s+([\d,]+)\s+[\d.]+%\s+([\d,]+)\s+"
        r"[\d.]+%\s+([\d,]+)\s+[\d.]+%\s+([\d,]+)\s+[\d.]+%\s+([\d,]+)\s*$",
        second, re.M)
    if not candidates or not origins:
        raise ValueError("could not find 110 Tongce candidate tables")
    current, _, registered = map(as_int, candidates.groups())
    professional, comprehensive, practical, ordinary, other, reported = map(
        as_int, origins.groups())
    if registered != reported:
        raise ValueError("Tongce tables disagree on registrations")
    return {"current": current, "registered": registered,
            "vocational": professional + practical, "ordinary": ordinary,
            "comprehensive": comprehensive, "other": other}

def published_inputs():
    return {row["metric"]: as_int(row["value"])
            for row in tsvio.read_rows(data_path("assessment-pool-inputs.tsv"))}


def overlap(xuece, tongce, graduates):
    tongce_current = tongce["current"] / tongce["registered"]
    xuece_current = xuece["current"] / xuece["total"]
    vocational = xuece["vocational"] * xuece_current / graduates["vocational"]
    academic = min(1.0, xuece["ordinary"] * xuece_current / graduates["academic"])
    rates = {"vocational": vocational, "ordinary": academic,
             "comprehensive": (vocational + academic) / 2,
             "other": xuece["current"] / graduates["total"]}
    return {group: tongce[group] * tongce_current * rates[group] for group in rates}

def main(out_path=None, tongce_source=None):
    xuece_source = glob.glob(source_path(GSAT))
    if len(xuece_source) != 1:
        raise ValueError(
            f"expected one 110 Xuece registration workbook, got {xuece_source}")
    xuece = xuece_counts(xuece_source[0])
    tongce = tongce_counts(tongce_source or source_path(TONGCE))
    estimated = overlap(xuece, tongce, published_inputs())
    total = round(xuece["current"] + tongce["current"] - sum(estimated.values()))
    row = {"year": YEAR, "percentile_counts": "Xuece, Tongce, Zhikao", "B": total,
           "B_display": f"{total / 1000:.0f}k", "cohort_scaled": "no",
           "source": "current Xuece and Tongce registrations minus track-mix overlap; "
                     "Zhikao subset"}
    tsvio.write_rows(out_path or path("assessment-pool.tsv"), [row])
    print(f"wrote {total:,} candidates; estimated Xuece-Tongce overlap "
          f"{sum(estimated.values()):,.0f}", file=sys.stderr)


if __name__ == "__main__":
    main()
