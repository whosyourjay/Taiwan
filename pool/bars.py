"""Turn admission rows into the bars a factor fit compares.

A department admitting through more than one path publishes more than one bar
for the same margin. Most paths publish a single percentile inside one exam's
takers. 繁星 publishes two facts at once: how far down a school's class rank it
reached, and which 學測 檢定 gates its admits had to clear on the way. That
second fact is what lets a fit tell a noisy measurement from a selective one.
"""

import collections
import re

import rank_uac
from pool import factor

# A gate reads as subject, band, and the 級分 that band stood at that year.
GATE = re.compile(r"(\S+?)(?:頂標|前標|均標|後標|底標)(\d+)")
RANK_PATH = "star"


class Bar:
    """One published cutoff, with whatever else its admitted group cleared."""

    def __init__(self, exam, seats, top=None, score=None, gates=()):
        self.exam = exam
        self.seats = float(seats)
        self.top = top
        self.score = score
        self.gates = tuple(gates)


def star_gates(row, cohort):
    """Share of 學測 takers clearing each 檢定 gate the row set.

    A gate almost nobody fails says nothing about who was admitted, so it goes
    the way a non-binding 篩選 does.
    """
    out = []
    for subject, level in GATE.findall(row["gates"]):
        top = cohort.top_fraction(row["year"], subject, level)
        if top is not None and top < rank_uac.NON_BINDING:
            out.append(top)
    return out


def bar_of(row, exam, top_of, cohort):
    """The bar a row publishes, or None where it publishes nothing usable."""
    if row["path"] == RANK_PATH:
        if not row.get("gpa"):
            return None
        return Bar(exam, row["seats"], score=factor.rank_score(float(row["gpa"])),
                   gates=star_gates(row, cohort))
    top = top_of(row)
    return None if top is None else Bar(exam, row["seats"], top=top)


def bucket_of(row, exam):
    """Bars that read the same way share a bucket and average together."""
    return factor.RANK if row["path"] == RANK_PATH else exam


def merge(bars):
    """Collapse one department's bars in a bucket into a single bar.

    Plain bars average by seats, as two readings of one margin should. A rank
    bar carries its own gates, so the largest stands for the group instead.
    """
    seats = sum(bar.seats for bar in bars)
    if bars[0].top is None:
        best = max(bars, key=lambda bar: bar.seats)
        return Bar(best.exam, seats, score=best.score, gates=best.gates)
    top = sum(bar.top * bar.seats for bar in bars) / seats
    return Bar(bars[0].exam, seats, top=top)


def observations(rows, exam_of, top_of, cohort, key=None):
    """Group rows by department, then pair every bucket that department filled."""
    if key is None:
        key = lambda row: (row["year"], row["school"], row["dept"])
    groups = collections.defaultdict(lambda: collections.defaultdict(list))
    for row in rows:
        exam = exam_of(row)
        if exam is None:
            continue
        bar = bar_of(row, exam, top_of, cohort)
        if bar is not None:
            groups[key(row)][bucket_of(row, exam)].append(bar)

    out = []
    for group, by_bucket in groups.items():
        merged = {name: merge(found) for name, found in by_bucket.items()}
        names = sorted(merged)
        pairs = [(merged[left], merged[right],
                  min(merged[left].seats, merged[right].seats))
                 for i, left in enumerate(names) for right in names[i + 1:]]
        if pairs:
            out.append((group, pairs))
    return out


def flatten(groups):
    """Flatten a sequence of ``(department, bars)`` pairs."""
    return [pair for _, pairs in groups for pair in pairs]


def counts(observations):
    """How many pairs join each kind of bar to each other."""
    got = collections.Counter()
    for left, right, _ in observations:
        names = sorted((factor.RANK if left.top is None else left.exam,
                        factor.RANK if right.top is None else right.exam))
        got[tuple(names)] += 1
    return got
