"""Read a published bar as noisy evidence about ability rather than as a place.

A cutoff is a score on one exam, not a rank in the cohort. Model ability as a
standard normal over the cohort and every measurement as

    M = λ A + sqrt(1 - λ²) ε

with ε independent of ability and of every other measurement. At λ = 1 clearing
a bar and holding an ability are the same fact, which is what the density models
assume. Below 1 the students at a bar are a mix of ability and luck, so their
expected ability sits closer to the middle than the bar reads.

Participation is unchanged and still carries the weight it did: each exam keeps
its own taker density over cohort ability, and a bar is a percentile inside that
pool. What λ adds is the shrinkage no reshaping of those densities can produce.

繁星 is what makes λ identifiable. It reports a class-rank bar and a set of 學測
檢定 gates for the same admitted group, and the rate at which a stricter gate
buys a looser rank bar is fixed by the correlation between the two measurements.
Conditional independence given ability turns every probability here into one
integral over ability, which Gauss-Hermite settles in a few vector operations.
"""

import math

import numpy as np
from numpy.polynomial import hermite_e
from scipy import optimize, special

from pool import complement, model

# 繁星's margin is a rank inside a school, not a score on any exam.
RANK = "rank"
LOADED = ("gsat", "tongce", "zhikao", RANK)
# Wide enough to hold any bar a normal score can reach, fine enough to invert.
BARS = np.linspace(-5.0, 5.0, 801)
CEILING = 0.999


def quadrature(nodes):
    """Standard-normal ability nodes and the probability weight of each."""
    ability, weights = hermite_e.hermegauss(nodes)
    return ability, weights / weights.sum()


def survival(z):
    """Share of a standard normal above `z`."""
    return special.ndtr(-z)


def rank_score(percentile):
    """Normal score of a within-school rank, where 1% beats 17%.

    Rank inside a school is uniform by construction, so its normal score is
    standard normal over the cohort however the schools differ. Whatever those
    differences are lands in this measurement's noise term.
    """
    return special.ndtri(1.0 - np.asarray(percentile, dtype=float) / 100.0)


class Gates:
    """Every 檢定 bar flattened, with the row each one came from.

    A row's gates are simultaneous requirements on different subjects, so the
    chance an ability clears all of them is a product. Flattening lets one
    vector operation cover every gate in the fit.
    """

    def __init__(self, per_row):
        self.counts = np.array([len(row) for row in per_row], dtype=int)
        self.flat = np.array([top for row in per_row for top in row], dtype=float)
        starts = np.concatenate([[0], np.cumsum(self.counts)[:-1]])
        self.starts = np.clip(starts, 0, max(len(self.flat) - 1, 0))

    def factor(self, pool, exam):
        """Chance a student at each ability node clears every gate in the row."""
        shape = (len(self.counts), len(pool.ability))
        if not len(self.flat):
            return np.ones(shape)
        bars = pool.threshold(exam, self.flat)
        loading, spread = pool.pair(exam)
        z = (bars[:, None] - loading * pool.ability) / spread
        logs = np.log(np.clip(survival(z), 1e-12, None))
        summed = np.add.reduceat(logs, self.starts, axis=0)
        summed[self.counts == 0] = 0.0
        return np.exp(summed)


class FactorPool:
    """A participation model plus one noise level per measurement.

    `pool` supplies each exam's taker density over cohort ability, so this wraps
    whatever density family the participation fit chose. `loadings` gives each
    measurement's correlation with ability.
    """

    def __init__(self, pool, loadings, nodes=96):
        self.pool = pool
        self.loadings = {k: min(float(v), CEILING) for k, v in loadings.items()}
        self.exams = pool.exams
        self.sizes = pool.sizes
        self.bins = pool.bins
        self.ability, self.weight = quadrature(nodes)
        self.takers = {exam: self._takers(exam) for exam in self.exams}
        self._tails = {}

    def _takers(self, exam):
        """Probability weights over ability among one exam's takers."""
        breaks = np.linspace(0.0, 1.0, self.bins + 1)
        density = np.interp(special.ndtr(self.ability), breaks, self.pool.values[exam])
        weights = self.weight * density
        return weights / weights.sum()

    def pair(self, measure):
        """A measurement's loading and the spread of its noise."""
        loading = self.loadings[measure]
        return loading, math.sqrt(1.0 - loading * loading)

    def tail(self, exam, bars, measure=None):
        """Share of an exam's takers scoring above each bar."""
        loading, spread = self.pair(measure or exam)
        z = (np.asarray(bars, dtype=float)[:, None] - loading * self.ability) / spread
        return survival(z) @ self.takers[exam]

    def threshold(self, exam, tops, measure=None):
        """The bar whose upper tail holds each given share of the takers."""
        key = (exam, measure)
        if key not in self._tails:
            self._tails[key] = self.tail(exam, BARS, measure)
        got = self._tails[key]
        return np.interp(np.asarray(tops, dtype=float), got[::-1], BARS[::-1])

    def implied(self, exam, bars, measure=None, gates=None):
        """Cohort percentile of the expected ability of a student at the bar.

        Conditioning on gates is what separates a loading from a density: it
        moves the answer for a fixed bar, and only the correlation says by how
        much.
        """
        loading, spread = self.pair(measure or exam)
        z = (np.asarray(bars, dtype=float)[:, None] - loading * self.ability) / spread
        weights = self.takers[exam] * np.exp(-0.5 * z * z)
        if gates is not None:
            weights = weights * gates
        total = weights.sum(axis=1)
        mean = np.divide((weights * self.ability).sum(axis=1), total,
                         out=np.zeros_like(total), where=total > 0)
        return special.ndtr(mean)

    def implied_top(self, exam, tops):
        """Where a plain within-exam top fraction lands on the cohort."""
        return self.implied(exam, self.threshold(exam, tops))

    def implied_rank(self, exam, scores, gates):
        """Where a class-rank bar lands, given the 學測 gates it sits behind."""
        return self.implied(exam, scores, measure=RANK, gates=gates)

    def abilities(self, exam, top_fractions):
        """Match the density models, so plain bars read the same way."""
        return self.implied_top(exam, top_fractions)


class Bars:
    """Bar pairs packed so one cost evaluation is a handful of vector ops."""

    def __init__(self, observations, exams):
        index = {exam: i for i, exam in enumerate(exams)}
        self.exams = list(exams)
        self.side = []
        for which in (0, 1):
            bars = [row[which] for row in observations]
            self.side.append({
                "exam": np.array([index[bar.exam] for bar in bars]),
                "top": np.array([bar.top or 0.0 for bar in bars], dtype=float),
                "score": np.array([bar.score or 0.0 for bar in bars], dtype=float),
                "ranked": np.array([bar.top is None for bar in bars]),
                "gates": Gates([bar.gates for bar in bars]),
            })
        self.weights = np.array([row[2] for row in observations], dtype=float)
        self.weight_sum = float(self.weights.sum())

    def side_abilities(self, pool, side):
        """Where every bar on one side of the pairs lands on the cohort."""
        out = np.empty(len(side["top"]))
        gates = None
        for i, exam in enumerate(self.exams):
            plain = (side["exam"] == i) & ~side["ranked"]
            if plain.any():
                out[plain] = pool.implied_top(exam, side["top"][plain])
            ranked = (side["exam"] == i) & side["ranked"]
            if ranked.any():
                if gates is None:
                    gates = side["gates"].factor(pool, exam)
                out[ranked] = pool.implied_rank(exam, side["score"][ranked],
                                                gates[ranked])
        return out

    def gaps(self, pool):
        """Disagreement between the two bars of every pair."""
        left, right = (self.side_abilities(pool, side) for side in self.side)
        self.levels = np.concatenate([left, right])
        return left - right

    def scatter(self, pool):
        """Weighted variance of every implied level the model produced."""
        self.gaps(pool)
        weights = np.concatenate([self.weights, self.weights])
        mean = float((weights * self.levels).sum()) / weights.sum()
        spread = self.levels - mean
        return float((weights * spread * spread).sum()) / weights.sum()


def disagreement(pool, observations, exams):
    """Seat-weighted mean absolute gap, in cohort percentile points."""
    if not observations:
        return 0.0
    packed = Bars(observations, exams)
    gaps = np.abs(packed.gaps(pool))
    return 100.0 * float((packed.weights * gaps).sum()) / packed.weight_sum


def _cost(packed):
    """Squared disagreement as a share of the level variance it left standing.

    Shrinking every loading at once pulls each implied level toward the middle,
    which cuts the raw gaps without explaining a thing. Dividing by the spread
    of the levels removes that escape and asks the fit for agreement it earned.
    """
    def evaluate(pool):
        gaps = packed.gaps(pool)
        error = float((packed.weights * gaps * gaps).sum()) / packed.weight_sum
        return error / max(packed.scatter(pool), 1e-9)

    return evaluate


def _unpack(params, nodes, loadings):
    """Split the optimiser vector into densities and one loading per measure."""
    share, retake = complement.pack(params, nodes)
    return share, retake, dict(zip(loadings, params[2 * nodes:]))


def fit(observations, sizes, segments, loadings=LOADED, nodes=96, floor=0.2,
        **hypotheses):
    """Fit the participation densities and every loading together."""
    if not observations:
        raise ValueError("no matched departments to fit against")
    exams = sorted(sizes)
    packed = Bars(observations, exams)
    cost = _cost(packed)
    count = segments + 1
    start = np.concatenate([
        complement.start(count, sizes, hypotheses.get("zero_tail", False)),
        np.full(len(loadings), 0.9),
    ])
    bounds = ([(0.0, 1.0)] * count
              + [(0.0, model.cohort_size(sizes) / sizes[complement.RETAKE])] * count
              + [(floor, CEILING)] * len(loadings))

    def objective(params):
        share, retake, found = _unpack(params, count, loadings)
        return cost(FactorPool(complement.ComplementPool(share, retake, sizes),
                               found, nodes))

    got = optimize.minimize(
        objective, start, method="SLSQP", bounds=bounds,
        constraints=complement.constraints(count, sizes, **hypotheses),
        options={"maxiter": 200, "ftol": 1e-9},
    )
    share, retake, found = _unpack(got.x, count, loadings)
    pool = FactorPool(complement.ComplementPool(share, retake, sizes), found, nodes)
    pool.degrees = complement.degrees(segments, hypotheses.get("zero_tail", False))
    pool.degrees += len(loadings)
    pool.converged = got.success
    return pool, disagreement(pool, observations, exams)
