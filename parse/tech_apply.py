"""Parse 四技日間部申請入學 weighted 學測 screening thresholds.

The result report supplies each program's weighted-average cutoff. Its program
workbook supplies the weights, admission quota and intended second-stage count.
Joining on 志願代碼 recovers a weighted raw 學測 total that can be read against
the national subject distributions.
"""

import re
import sys

from lib import tsvio
from lib.paths import data_path, path
from parse.uac import pdf_text


GSAT_MAX = 15.0
WEIGHT_SUFFIX = "權重"
CODE = re.compile(r"^\s*(\d{6})\s+")
DECIMAL = re.compile(r"(?<!\d)(\d+\.\d+)(?!\d)")


def _clean_header(value):
    return re.sub(r"\s+", "", str(value))


def workbook_rows(source):
    """Yield program dictionaries from the official XLS workbook."""
    import xlrd

    sheet = xlrd.open_workbook(source).sheet_by_index(0)
    rows = (sheet.row_values(i) for i in range(sheet.nrows))
    iterator = iter(rows)
    headers = [_clean_header(value) for value in next(iterator)]
    for values in iterator:
        yield dict(zip(headers, (str(value).strip() for value in values)))


def screen_cutoffs(text):
    """Return 志願代碼 -> primary 學測 weighted-average screening score."""
    cutoffs = {}
    for line in text.splitlines():
        match = CODE.match(line)
        if not match:
            continue
        decimals = DECIMAL.findall(line[match.end():])
        if decimals:
            cutoffs[match.group(1)] = float(decimals[0])
    return cutoffs


def _integer(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def formula_of(program):
    """Weighted native 學測 formula in the repository's subjectxweight syntax."""
    subjects = []
    for header, value in program.items():
        if not header.endswith(WEIGHT_SUFFIX):
            continue
        try:
            weight = float(value)
        except ValueError:
            continue
        if weight > 0:
            subjects.append((header.removesuffix(WEIGHT_SUFFIX), weight))
    return subjects


def raw_cutoff(screen, subjects):
    """Undo JCTV's 0-100 weighted average to a weighted 0-15 級分 sum."""
    return float(screen) / 100.0 * GSAT_MAX * sum(weight for _, weight in subjects)


def parse_pair(report, rules, year):
    cutoffs = screen_cutoffs(pdf_text(report))
    rows = []
    for program in workbook_rows(rules):
        code = program.get("志願代碼", "").split(".", 1)[0]
        subjects = formula_of(program)
        seats = _integer(program.get("招生名額"))
        if code not in cutoffs or not subjects or not seats:
            continue
        screen = cutoffs[code]
        total_weight = sum(weight for _, weight in subjects)
        rows.append({
            "year": str(year),
            "code": code,
            "school": program["學校"],
            "dept": program["系（組）、學程名稱"],
            "subjects": " ".join(f"{s}x{w:.2f}" for s, w in subjects),
            "total_weight": round(total_weight, 2),
            "seats": seats,
            "screened": _integer(program.get("預計複試人數")),
            "screen": screen,
            "cutoff": round(raw_cutoff(screen, subjects), 4),
            "norm": round(screen / 100.0, 4),
        })
    return rows, len(cutoffs)


def main(out_path):
    year = "110"
    report = path("tech", f"jctv-{year}-xuece-screen.pdf")
    rules = path("tech", f"jctv-{year}-xuece-rules.xls")
    rows, reported = parse_pair(report, rules, year)
    print(f"{year}: {len(rows)} of {reported} reported thresholds joined", file=sys.stderr)
    written = tsvio.write_rows(out_path, rows)
    print(f"wrote {written} rows to {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main(data_path("tech-apply-cutoffs.tsv"))
