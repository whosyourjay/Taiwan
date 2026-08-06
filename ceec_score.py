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
            total = sum(counts.values())
            below = 0.0
            percentiles, scores = [], []
            for score, count in sorted(counts.items()):
                # Candidates tied in a score bin share its midrank.
                percentiles.append((below + count / 2) / total)
                scores.append(score)
                below += count
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
