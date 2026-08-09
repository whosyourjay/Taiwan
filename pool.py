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

    def abilities(self, exam, top_fractions):
        """Cohort percentile of each bar that its top fraction clears, 0-1.

        `cum[k]` is the share of takers at or above the foot of bin k, so it
        falls from 1 to 0 and locating a bar is one search per array.
        """
        share = self.shares[exam]
        cum = np.concatenate([np.cumsum(share[::-1])[::-1], [0.0]])
        tops = np.clip(np.asarray(top_fractions, dtype=float), 0.0, 1.0)
        # cum reversed runs 0 to 1, so the search lands on cum[k] >= t > cum[k+1].
        k = self.bins - np.searchsorted(cum[::-1], tops, side="left")
        k = np.clip(k, 0, self.bins - 1)
        return (k + 1) / self.bins - (tops - cum[k + 1]) / (share[k] * self.bins)

    def ability(self, exam, top_fraction):
        """Cohort percentile of the bar that the top `top_fraction` clears."""
        return float(self.abilities(exam, [top_fraction])[0])

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


class _Problem:
    """Observations packed into arrays so a cost evaluation is a few vector ops."""

    def __init__(self, observations, exams, bins):
        index = {e: i for i, e in enumerate(exams)}
        self.exams = list(exams)
        self.bins = bins
        self.side = []
        for which in (0, 2):
            self.side.append((
                np.array([index[o[which]] for o in observations]),
                np.array([o[which + 1] for o in observations], dtype=float),
            ))
        self.weights = np.array([o[4] for o in observations], dtype=float)
        self.weight_sum = float(self.weights.sum())

    def gaps(self, pool):
        out = []
        for exam_ids, tops in self.side:
            got = np.empty(len(tops))
            for i, exam in enumerate(self.exams):
                mask = exam_ids == i
                if mask.any():
                    got[mask] = pool.abilities(exam, tops[mask])
            out.append(got)
        return out[0] - out[1]


def _cost(params, problem, smooth):
    pool = AbilityPool(_shares_from(params, problem.exams, problem.bins),
                       problem.bins)
    gaps = problem.gaps(pool)
    cost = float((problem.weights * gaps * gaps).sum()) / problem.weight_sum
    # Without this the fit is free to spike one bin, which fits a few matched
    # departments and says nothing about the cohort.
    for exam in problem.exams:
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
    problem = _Problem(observations, exams, bins)
    rng = np.random.default_rng(seed)
    best = None
    for attempt in range(restarts):
        start = np.zeros(len(exams) * bins) if attempt == 0 else rng.normal(
            0.0, 1.0, len(exams) * bins
        )
        got = optimize.minimize(
            _cost, start, args=(problem, smooth), method="Powell",
            options={"maxiter": 4000, "xtol": 1e-6, "ftol": 1e-9},
        )
        if best is None or got.fun < best.fun:
            best = got
    pool = AbilityPool(_shares_from(best.x, exams, bins), bins)
    return pool, residual(pool, observations)


def residual(pool, observations):
    """Seat-weighted mean absolute disagreement, in cohort percentile points."""
    if not observations:
        return 0.0
    exams = sorted({e for o in observations for e in (o[0], o[2])})
    problem = _Problem(observations, exams, pool.bins)
    gaps = np.abs(problem.gaps(pool))
    return 100.0 * float((problem.weights * gaps).sum()) / problem.weight_sum


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
