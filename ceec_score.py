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


def interpolate(xs, ys, x, extrapolate=False):
    """Linear interpolation, held constant beyond the observed endpoints.

    With `extrapolate`, the end segments continue instead of flattening.
    """
    i = bisect.bisect_right(xs, x)
    if i == 0:
        if not extrapolate:
            return ys[0]
        i = 1
    elif i == len(xs):
        if not extrapolate:
            return ys[-1]
        i = len(xs) - 1
    x0, x1 = xs[i - 1], xs[i]
    y0, y1 = ys[i - 1], ys[i]
    if x1 == x0:
        return y0
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
    def load(cls, path):
        with open(path, encoding="utf-8") as f:
            return cls(csv.DictReader(f, delimiter="\t"))

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

    def formula_percentile(self, year, formula, cutoff):
        """Return the equal-subject percentile matching a weighted total.

        Returns None when a formula contains an exam without a CEEC distribution,
        currently only 術科.
        """
        subjects = []
        for token in formula.split():
            subject, weight = token.rsplit("x", 1)
            key = self.subject_key(year, subject)
            if key is None:
                return None
            subjects.append((key, float(weight)))
        if not subjects:
            return None

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
