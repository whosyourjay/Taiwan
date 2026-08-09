"""Convert a weighted UAC cutoff to an equivalent CEEC subject percentile.

The UAC tables publish only the weighted total at the admission margin, not the
admitted student's score in each subject.  Marginal CEEC distributions cannot
recover that missing joint score vector.  We use the smallest explicit model:
the marginal student is at the same percentile in every subject in the formula.
The percentile whose subject quantiles reproduce the published weighted total
is the row's comparable score.
"""

import bisect
import collections
import csv

from parse import tcte


SUBJECT_NAMES = {
    "國": "國文",
    "英": "英文",
    "數甲": "數學甲",
    "數乙": "數學乙",
    "物": "物理",
    "化": "化學",
    "生": "生物",
    "歷": "歷史",
    "地": "地理",
    "公": "公民與社會",
    "數A": "數學A",
    "數B": "數學B",
    "社": "社會",
    "自": "自然",
}
XUECE_SUBJECTS = {"國", "英", "數A", "數B", "社", "自"}


def weighted_midpoints(rows, field):
    """Return sorted values and their seat-weighted midrank percentiles."""
    counts = collections.Counter()
    for row in rows:
        counts[row[field]] += row["seats"]
    return midranks(counts)


def midranks(counts):
    """Return sorted values and midranks from a value -> weight mapping."""
    total = sum(counts.values())
    below = 0.0
    values, percentiles = [], []
    for value, count in sorted(counts.items()):
        values.append(value)
        percentiles.append((below + count / 2) / total)
        below += count
    return values, percentiles


def interpolate(xs, ys, x):
    """Linear interpolation, held constant beyond the observed endpoints."""
    i = bisect.bisect_right(xs, x)
    if i == 0:
        return ys[0]
    if i == len(xs):
        return ys[-1]
    x0, x1 = xs[i - 1], xs[i]
    y0, y1 = ys[i - 1], ys[i]
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def calibrate_fallbacks(rows):
    """Put rows missing a CEEC distribution onto the same within-year scale.

    A raw fraction and a candidate percentile are not directly comparable.  For
    each year, preserve a fallback row's seat position in the raw `norm`
    distribution, then map that position to the supported rows' CEEC-percentile
    distribution.  This retains the evidence available for 術科 without
    inventing a distribution for it.
    """
    by_year = collections.defaultdict(list)
    for row in rows:
        by_year[row["year"]].append(row)

    calibrated = 0
    for group in by_year.values():
        supported = [row for row in group if "ceec_percentile" in row]
        missing = [row for row in group if "ceec_percentile" not in row]
        if not supported:
            continue
        norms, norm_percentiles = weighted_midpoints(supported, "norm")
        ceec_values, ceec_percentiles = weighted_midpoints(
            supported, "ceec_percentile"
        )
        for row in missing:
            position = interpolate(norms, norm_percentiles, row["norm"])
            row["basis"] = interpolate(ceec_percentiles, ceec_values, position)
            row["ceec_fallback"] = True
            calibrated += 1
    return calibrated


# Longest first, so 數學A is never read as 數學 followed by a stray A. CAC prints
# both the full names and one-character abbreviations, sometimes in one table.
GSAT_TOKENS = ["數學A", "數學B", "國文", "英文", "數學", "社會", "自然", "英聽",
               "數A", "數B", "國", "英", "數", "社", "自"]
GSAT_FULL = {"數A": "數學A", "數B": "數學B", "國": "國文", "英": "英文",
             "數": "數學", "社": "社會", "自": "自然"}


def split_subjects(label):
    """Split a 篩選 label such as 國英數自 into full subject names, or None.

    Returns None rather than a partial list, so an unrecognised label is dropped
    instead of being scored against the wrong set of subjects.
    """
    if not label:
        return None
    out, i = [], 0
    while i < len(label):
        for token in GSAT_TOKENS:
            if label.startswith(token, i):
                out.append(GSAT_FULL.get(token, token))
                i += len(token)
                break
        else:
            return None
    return out


class CohortPercentiles:
    """學測 級分 distributions over everyone who sat the exam.

    Unlike a rank within the rows we happened to collect, this is an absolute
    quantity: it is referenced to the national cohort, so a department's number
    does not move when another school is added to or missing from the sample.

    CEEC publishes the distribution of every 2-4 subject total alongside the
    single subjects, so a 國英數自 bar is a direct lookup. Nothing here assumes
    the subjects are independent, or perfectly correlated, or anything else.
    """

    def __init__(self, rows):
        self.counts = collections.defaultdict(collections.Counter)
        for row in rows:
            if row["exam"] != "gsat":
                continue
            seats = float(row["seats"])
            if seats > 0:
                self.counts[(str(row["year"]), row["subject"])][float(row["score"])] += seats

    @classmethod
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(csv.DictReader(f, delimiter="\t"))

    def top_fraction(self, year, label, level):
        """Share of the cohort scoring at or above `level` on `label`, or None.

        None means the label named a subject set with no published distribution,
        which is currently only 英聽 — reported as bands, not 級分.
        """
        subjects = split_subjects(label)
        if not subjects:
            return None
        counts = self.counts.get((str(year), "、".join(subjects)))
        if not counts:
            return None
        total = sum(counts.values())
        return sum(n for score, n in counts.items() if score >= float(level)) / total


class ScoreDistributions:
    def __init__(self, rows):
        grouped = collections.defaultdict(collections.Counter)
        for row in rows:
            count = float(row["seats"])
            if count > 0:
                key = (str(row["year"]), row["exam"], row["subject"])
                grouped[key][float(row["score"])] += count

        self.quantiles = {}
        for key, counts in grouped.items():
            scores, percentiles = midranks(counts)
            self.quantiles[key] = (percentiles, scores)

    @classmethod
    def load(cls, *paths):
        rows = []
        for path in paths:
            with open(path, encoding="utf-8") as f:
                rows.extend(csv.DictReader(f, delimiter="\t"))
        return cls(rows)

    def subjects(self, year, exam):
        """Every subject name published for one exam in one year."""
        return {s for y, e, s in self.quantiles if y == str(year) and e == exam}

    def subject_key(self, year, subject):
        """Map a UAC formula abbreviation to its CEEC exam and subject name."""
        name = SUBJECT_NAMES.get(subject)
        if not name:
            return None
        exam = "xuece" if int(year) >= 111 and subject in XUECE_SUBJECTS else "zhikao"
        key = (str(year), exam, name)
        return key if key in self.quantiles else None

    def subject_score(self, key, percentile):
        """Linearly interpolate a subject's score at a candidate percentile."""
        percentiles, scores = self.quantiles[key]
        return interpolate(percentiles, scores, percentile)

    def tongce_key(self, year, subject, group):
        """Map a 統測 formula subject to its distribution, given the row's 群(類).

        國文 and 英文 are one paper nationally and 數學 is pooled over its four,
        but each 專業科目 belongs to a 群, so that name has to be looked up.
        """
        if subject.startswith("專業"):
            subject = tcte.professional_subject(
                group, subject, self.subjects(year, "tongce")
            )
            if subject is None:
                return None
        key = (str(year), "tongce", subject)
        return key if key in self.quantiles else None

    def weighted_subjects(self, formula, key_of):
        """Resolve `subjectxweight` tokens to distribution keys, or None."""
        subjects = []
        for token in formula.split():
            subject, weight = token.rsplit("x", 1)
            key = key_of(subject)
            if key is None:
                return None
            subjects.append((key, float(weight)))
        return subjects or None

    def solve(self, subjects, cutoff):
        """The equal-subject percentile whose quantiles sum to `cutoff`."""
        cutoff = float(cutoff)
        low, high = 0.0, 1.0
        for _ in range(40):
            percentile = (low + high) / 2
            total = sum(
                weight * self.subject_score(key, percentile)
                for key, weight in subjects
            )
            if total < cutoff:
                low = percentile
            else:
                high = percentile
        return (low + high) / 2

    def formula_percentile(self, year, formula, cutoff):
        """Return the equal-subject percentile matching a weighted total.

        Returns None when a formula contains an exam without a CEEC distribution,
        currently only 術科.
        """
        subjects = self.weighted_subjects(
            formula, lambda s: self.subject_key(year, s)
        )
        return self.solve(subjects, cutoff) if subjects else None

    def tongce_percentile(self, year, formula, cutoff, group):
        """The same reading of a 統測 weighted total, against 統測's own takers."""
        subjects = self.weighted_subjects(
            formula, lambda s: self.tongce_key(year, s, group)
        )
        return self.solve(subjects, cutoff) if subjects else None
