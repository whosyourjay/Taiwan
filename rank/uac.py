"""Load and normalize Taiwan university admission threshold rows.

This module is deliberately limited to source interpretation. It does not rank
departments or translate one admission route onto another. Production scoring
belongs to :mod:`pool.ability`, where each year's published thresholds are read
through that year's independently tiled exam curves.
"""

import collections
import difflib

from lib import deptname, tsvio
from lib.paths import data_path


SOURCES = {"uac": "uac-cutoffs.tsv", "tech": "tech-cutoffs.tsv"}
EXTRA = {
    "star": "star-cutoffs.tsv",
    "star_eight": "star-cutoffs.tsv",
    "apply": "apply-cutoffs.tsv",
}
NON_BINDING = 0.95
OCR_MATCH = 0.80
OCR_MARGIN = 0.15


def identify_department(row):
    """Preserve the source 系組 name, then attach its reporting department."""
    row["application_group"] = row["dept"].strip()
    row["dept"] = deptname.normalize(row["application_group"])


def load(system, distributions=None):
    """Load normalized rows for 分發入學 or 四技二專聯合登記分發."""
    for row in tsvio.read_rows(data_path(SOURCES[system])):
        row["system"] = system
        row["path"] = system
        identify_department(row)
        row["seats"] = int(row["seats"])
        row["norm"] = float(row["norm"])
        if distributions is not None:
            percentile = (
                distributions.formula_percentile(
                    row["year"], row["subjects"], row["cutoff"]
                )
                if system == "uac"
                else distributions.tongce_percentile(
                    row["year"], row["subjects"], row["cutoff"], row["group"]
                )
            )
            if percentile is not None:
                row["ceec_percentile"] = percentile
        yield row


def load_star(group="one2seven", cohort=None):
    """Load 繁星 rows with class-rank and every binding 學測 gate intact."""
    for row in tsvio.read_rows(data_path(EXTRA["star"])):
        admitted = int(row["admitted"] or 0)
        if row["group"] != group or not row["gpa"] or not admitted:
            continue
        row["system"] = "uac"
        row["path"] = "star" if group == "one2seven" else "star_eight"
        row["school"] = row["college"]
        identify_department(row)
        row["screened"] = admitted
        row["seats"] = int(row["quota"] or 0) if group == "eight" else admitted
        if not row["seats"]:
            continue
        row["norm"] = -float(row["gpa"])
        row["class_pct"] = 100.0 - float(row["gpa"])
        row["xuece_tops"] = (
            [top for _, top in cohort.binding_gates(row["year"], row["gates"])]
            if cohort is not None else []
        )
        yield row


def load_apply(cohort):
    """Load readable 個人申請 first-stage screens and their admitted seats."""
    for row in tsvio.read_rows(data_path(EXTRA["apply"])):
        if not row["norm"] or not row["dept"].strip():
            continue
        norm = float(row["norm"])
        admitted = int(row["admitted"] or 0)
        if norm > 1 or not admitted:
            continue
        top = cohort.top_fraction(row["year"], row["cut_label"], row["cut_level"])
        if top is None or top >= NON_BINDING:
            continue
        row["system"], row["path"] = "uac", "apply"
        row["school"] = row["college"]
        identify_department(row)
        row["seats"] = admitted
        row["norm"] = norm
        row["cohort_top"] = top
        yield row


def joinable(rows, known):
    """Keep rows matching a 分發 department, repairing unambiguous OCR names."""
    by_school = collections.defaultdict(dict)
    for year, school, dept in known:
        by_school[(year, school)][deptname.key(dept)] = dept
    out = []
    for row in rows:
        candidates = by_school[(row["year"], row["school"])]
        key = deptname.key(row["dept"])
        if key in candidates:
            row["dept"] = candidates[key]
            out.append(row)
            continue
        if row.get("path") != "apply":
            continue
        matched = ocr_department(row["dept"], candidates)
        if matched:
            row["dept"] = matched
            out.append(row)
    return out


def ocr_department(source, candidates):
    """Return an unambiguous OCR repair from a school's known departments."""
    source = chinese_chars(source)
    if not source:
        return None
    scored = sorted(
        (difflib.SequenceMatcher(None, source, chinese_chars(value)).ratio(), value)
        for value in candidates.values()
    )
    if not scored:
        return None
    best, value = scored[-1]
    next_best = scored[-2][0] if len(scored) > 1 else 0.0
    return value if best >= OCR_MATCH and best - next_best >= OCR_MARGIN else None


def chinese_chars(value):
    """CJK department text, without OCR punctuation and Latin debris."""
    return "".join(char for char in value if "\u4e00" <= char <= "\u9fff")


def unify_spelling(rows):
    """Give each department the spelling that admitted the most students."""
    seats = collections.defaultdict(collections.Counter)
    for row in rows:
        seats[(row["school"], deptname.key(row["dept"]))][row["dept"]] += row["seats"]
    names = {key: counts.most_common(1)[0][0] for key, counts in seats.items()}
    for row in rows:
        row["dept"] = names[(row["school"], deptname.key(row["dept"]))]
