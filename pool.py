"""Put every exam's takers on one ability axis so their percentiles compare.

A percentile inside one exam's takers says nothing next to another's: 學測 is sat
by most of a 普通高中 cohort, 分科測驗 by the slice that did not already place,
統測 by 技術型高中. Ranking first in one is not ranking first in another.

Model each exam's takers as a density over ability, where ability is the
percentile in the whole cohort and so is uniform by construction. Hold that
density piecewise constant across a handful of bins and the conversion is
arithmetic: the top `p` of an exam's takers are those above the ability where
its own cumulative, counted from the top, reaches `p`.

The bin weights are fit to make the exams agree wherever one department admits
through more than one of them. Nothing here models how subjects correlate or how
noisy a score is; the only claim is that each exam draws a different slice of the
cohort, and that slice is what a percentile is relative to.
"""

import collections
import math

import numpy as np
from scipy import optimize


class AbilityPool:
    """Per-exam shares of takers across equal-width bins of cohort ability.

    `shares[exam]` sums to 1 over bins ordered from lowest ability to highest.
    """

    def __init__(self, shares, bins):
        self.shares = {e: np.asarray(s, dtype=float) for e, s in shares.items()}
        self.bins = bins

    def ability(self, exam, top_fraction):
        """Cohort percentile of the bar that the top `top_fraction` clears.

        Returns 0-1, where 1 is the top of the cohort.
        """
        share = self.shares[exam]
        remaining = float(np.clip(top_fraction, 0.0, 1.0))
        for k in range(self.bins - 1, -1, -1):
            if remaining <= share[k]:
                within = remaining / share[k] if share[k] else 0.0
                return (k + 1 - within) / self.bins
            remaining -= share[k]
        return 0.0

    def participation(self, exam, sizes):
        """Takers per bin as a fraction of the cohort slice that bin holds."""
        cohort = sum(sizes.values()) / self.bins
        return self.shares[exam] * sizes[exam] / cohort


def _shares_from(params, exams, bins):
    """Softmax each exam's free parameters into positive shares summing to 1."""
    out = {}
    for i, exam in enumerate(exams):
        raw = params[i * bins:(i + 1) * bins]
        raw = raw - raw.max()
        weights = np.exp(raw)
        out[exam] = weights / weights.sum()
    return out


def _cost(params, exams, bins, observations, smooth):
    pool = AbilityPool(_shares_from(params, exams, bins), bins)
    total = 0.0
    weight_sum = 0.0
    for exam_a, top_a, exam_b, top_b, weight in observations:
        gap = pool.ability(exam_a, top_a) - pool.ability(exam_b, top_b)
        total += weight * gap * gap
        weight_sum += weight
    cost = total / weight_sum if weight_sum else 0.0
    # Without this the fit is free to spike one bin, which fits a few matched
    # departments and says nothing about the cohort.
    for exam in exams:
        steps = np.diff(pool.shares[exam])
        cost += smooth * float((steps * steps).sum())
    return cost


def fit(observations, exams, bins=3, smooth=0.05, restarts=6, seed=20260809):
    """Fit per-exam bin shares so matched departments agree on ability.

    `observations` are (exam_a, top_a, exam_b, top_b, weight), each a department
    admitting through two exams, with the share of each exam's takers that
    cleared its bar. Returns (pool, mean_abs_disagreement).
    """
    if not observations:
        raise ValueError("no matched departments to fit against")
    rng = np.random.default_rng(seed)
    best = None
    for attempt in range(restarts):
        start = np.zeros(len(exams) * bins) if attempt == 0 else rng.normal(
            0.0, 1.0, len(exams) * bins
        )
        got = optimize.minimize(
            _cost, start, args=(exams, bins, observations, smooth), method="Powell",
            options={"maxiter": 20000, "xtol": 1e-6, "ftol": 1e-9},
        )
        if best is None or got.fun < best.fun:
            best = got
    pool = AbilityPool(_shares_from(best.x, exams, bins), bins)
    return pool, residual(pool, observations)


def residual(pool, observations):
    """Seat-weighted mean absolute disagreement, in cohort percentile points."""
    total = weight_sum = 0.0
    for exam_a, top_a, exam_b, top_b, weight in observations:
        gap = pool.ability(exam_a, top_a) - pool.ability(exam_b, top_b)
        total += weight * abs(gap)
        weight_sum += weight
    return 100.0 * total / weight_sum if weight_sum else 0.0


def matched(rows, exam_of, top_of, key=None):
    """Build observations from rows of departments admitting through two exams.

    Rows sharing `key` but sitting in different exams pair up. Each pair is
    weighted by the smaller intake, which is what limits how well the match
    locates the two bars against each other.
    """
    if key is None:
        key = lambda r: (r["year"], r["school"], r["dept"])
    groups = collections.defaultdict(lambda: collections.defaultdict(list))
    for row in rows:
        exam = exam_of(row)
        top = top_of(row)
        if exam is not None and top is not None:
            groups[key(row)][exam].append((top, row["seats"]))

    out = []
    for by_exam in groups.values():
        names = sorted(by_exam)
        for i, exam_a in enumerate(names):
            for exam_b in names[i + 1:]:
                out.append((exam_a, _mean(by_exam[exam_a]),
                            exam_b, _mean(by_exam[exam_b]),
                            min(_seats(by_exam[exam_a]), _seats(by_exam[exam_b]))))
    return out


def _mean(pairs):
    seats = sum(n for _, n in pairs)
    return sum(t * n for t, n in pairs) / seats if seats else math.nan


def _seats(pairs):
    return sum(n for _, n in pairs)
