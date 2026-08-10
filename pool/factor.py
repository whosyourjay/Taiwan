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

import collections
import math

import numpy as np
from numpy.polynomial import hermite_e
from scipy import optimize, special

from pool import complement, model

# 繁星's margin is a rank inside a school, not a score on any exam.
RANK = "rank"
LOADED = ("gsat", "tongce", "zhikao", RANK)
# Wide enough to hold any bar a normal score can reach, fine enough to invert.
BARS = np.linspace(-5.0, 5.0, 401)
# A sharp measurement turns its tail into a step, which even spacing in the
# cohort percentile resolves and normal-node spacing does not.
CELLS = 1024
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


def rank_percentile(score):
    """The within-school rank a normal score came from."""
    return 100.0 * (1.0 - special.ndtr(np.asarray(score, dtype=float)))


class Gates:
    """Every 檢定 bar flattened, with the row each one came from.

    A row's gates are simultaneous requirements on different subjects, so the
    chance an ability clears all of them is a product. Flattening lets one
    vector operation cover every gate in the fit.
    """

    def __init__(self, per_row):
        self.counts = np.array([len(row) for row in per_row], dtype=int)
        self.flat = np.array([top for row in per_row for top in row], dtype=float)
        self.rows = np.repeat(np.arange(len(self.counts)), self.counts)
        starts = np.concatenate([[0], np.cumsum(self.counts)[:-1]])
        self.starts = np.clip(starts, 0, max(len(self.flat) - 1, 0))

    def factor(self, pool, exam, ability):
        """Chance a student at each ability node clears every gate in its row.

        `ability` holds one row of nodes per bar, so each gate is tested against
        the nodes belonging to the bar that set it.
        """
        if not len(self.flat):
            return np.ones(ability.shape)
        bars = pool.threshold(exam, self.flat)
        loading, spread = pool.pair(exam)
        z = (bars[:, None] - loading * ability[self.rows]) / spread
        logs = np.log(np.clip(survival(z), 1e-300, None))
        summed = np.add.reduceat(logs, self.starts, axis=0)
        summed[self.counts == 0] = 0.0
        return np.exp(summed)


class FactorPool:
    """A participation model plus one noise level per measurement.

    `pool` supplies each exam's taker density over cohort ability, so this wraps
    whatever density family the participation fit chose. `loadings` gives each
    measurement's correlation with ability.
    """

    def __init__(self, pool, loadings, nodes=96, cells=CELLS):
        self.pool = pool
        self.loadings = {k: min(float(v), CEILING) for k, v in loadings.items()}
        self.exams = pool.exams
        self.sizes = pool.sizes
        self.bins = pool.bins
        self.ability, self.weight = quadrature(nodes)
        self.cell = special.ndtri((np.arange(cells) + 0.5) / cells)
        self.takers = {exam: self._takers(exam, cells) for exam in self.exams}
        self._tails = {}

    def density(self, exam, ability):
        """How thickly an exam draws its takers at each ability."""
        breaks = np.linspace(0.0, 1.0, self.bins + 1)
        return np.interp(special.ndtr(ability), breaks, self.pool.values[exam])

    def _takers(self, exam, cells):
        """Probability weights over even slices of the cohort, for one exam."""
        weights = self.density(exam, self.cell) / cells
        return weights / weights.sum()

    def pair(self, measure):
        """A measurement's loading and the spread of its noise.

        Splitting 統測 into its 數學 papers splits who sat it, not how sharply
        it reads, so those pools share one loading.
        """
        loading = self.loadings[complement.measure(measure)]
        return loading, math.sqrt(1.0 - loading * loading)

    def tail(self, exam, bars, measure=None):
        """Share of an exam's takers scoring above each bar."""
        loading, spread = self.pair(measure or exam)
        z = (np.asarray(bars, dtype=float)[:, None] - loading * self.cell) / spread
        return survival(z) @ self.takers[exam]

    def threshold(self, exam, tops, measure=None):
        """The bar whose upper tail holds each given share of the takers.

        Interpolating the tail on a probit scale rather than a linear one is
        what keeps a coarse grid honest: a tail is close to normal, so on that
        scale the curve being inverted is nearly a straight line.
        """
        key = (exam, measure)
        if key not in self._tails:
            got = np.clip(self.tail(exam, BARS, measure), 1e-12, 1 - 1e-12)
            self._tails[key] = special.ndtri(got)
        probit = self._tails[key]
        want = special.ndtri(np.clip(np.asarray(tops, dtype=float), 1e-12, 1 - 1e-12))
        return np.interp(want, probit[::-1], BARS[::-1])

    def posterior(self, bars, measure):
        """Ability nodes for a student sitting exactly at each bar.

        Before participation is counted, ability given a bar is normal about
        `λ m` with the noise the loading leaves. Centring the quadrature there
        keeps every node where the answer lives, however sharp the measurement
        gets, and the taker density then reweights those nodes.
        """
        loading, spread = self.pair(measure)
        return loading * np.asarray(bars, dtype=float)[:, None] + spread * self.ability

    def implied(self, exam, bars, measure=None, gates=None):
        """Cohort percentile of the expected ability of a student at the bar.

        Conditioning on gates is what separates a loading from a density: it
        moves the answer for a fixed bar, and only the correlation says by how
        much.
        """
        ability = self.posterior(bars, measure or exam)
        weights = self.weight * self.density(exam, ability)
        if gates is not None:
            weights = weights * gates.factor(self, exam, ability)
        total = weights.sum(axis=1)
        mean = np.divide((weights * ability).sum(axis=1), total,
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


class Side:
    """One side of every pair, split into the groups that read alike."""

    def __init__(self, bars, exams):
        self.size = len(bars)
        self.top = np.array([0.0 if bar.top is None else bar.top for bar in bars])
        self.score = np.array([bar.score or 0.0 for bar in bars], dtype=float)
        self.groups = []
        for exam in exams:
            here = np.array([bar.exam == exam for bar in bars])
            plain = np.flatnonzero(here & [bar.top is not None for bar in bars])
            ranked = np.flatnonzero(here & [bar.top is None for bar in bars])
            gates = Gates([bars[i].gates for i in ranked])
            self.groups.append((exam, plain, ranked, gates))

    def abilities(self, pool):
        """Where every bar on this side lands on the cohort."""
        out = np.empty(self.size)
        for exam, plain, ranked, gates in self.groups:
            if len(plain):
                out[plain] = pool.implied_top(exam, self.top[plain])
            if len(ranked):
                out[ranked] = pool.implied_rank(exam, self.score[ranked], gates)
        return out


class Bars:
    """Bar pairs packed so one cost evaluation is a handful of vector ops."""

    def __init__(self, observations, exams):
        self.exams = list(exams)
        self.side = [Side([row[which] for row in observations], self.exams)
                     for which in (0, 1)]
        self.weights = np.array([row[2] for row in observations], dtype=float)
        self.weight_sum = float(self.weights.sum())

    def levels(self, pool):
        """Where each pair's two bars land, as a (left, right) pair of arrays."""
        return self.side[0].abilities(pool), self.side[1].abilities(pool)

    def gaps(self, pool):
        """Disagreement between the two bars of every pair."""
        left, right = self.levels(pool)
        return left - right

    def scatter(self, left, right):
        """Weighted variance of every implied level the model produced."""
        levels = np.concatenate([left, right])
        weights = np.concatenate([self.weights, self.weights])
        mean = float((weights * levels).sum()) / weights.sum()
        spread = levels - mean
        return float((weights * spread * spread).sum()) / weights.sum()


def disagreement(pool, observations, exams):
    """Seat-weighted mean absolute gap, in cohort percentile points."""
    if not observations:
        return 0.0
    packed = Bars(observations, exams)
    gaps = np.abs(packed.gaps(pool))
    return 100.0 * float((packed.weights * gaps).sum()) / packed.weight_sum


def cost(packed, pool):
    """Squared disagreement as a share of the level variance it left standing.

    Shrinking every loading at once pulls each implied level toward the middle,
    which cuts the raw gaps without explaining a thing. Dividing by the spread
    of the levels removes that escape and asks the fit for agreement it earned.
    """
    left, right = packed.levels(pool)
    gaps = left - right
    error = float((packed.weights * gaps * gaps).sum()) / packed.weight_sum
    return error / max(packed.scatter(left, right), 1e-9)


def build(params, count, sizes, loadings, nodes):
    """Read one optimiser vector as densities wrapped in their loadings."""
    found = dict(zip(loadings, params[len(complement.EXAMS) * count:]))
    pool = model.LinearAbilityPool(complement.values(params, count), sizes)
    return FactorPool(pool, found, nodes)


def fit(observations, sizes, segments, loadings=LOADED, nodes=96, floor=0.2,
        overlap=0.0, nested=True, steps=60):
    """Fit the participation densities and every loading together.

    SLSQP differences the cost numerically, so a step costs one evaluation per
    parameter plus one. At full size an evaluation is about 80ms and a step
    about two seconds, so `steps` caps the whole fit near two minutes.
    `pool.converged` says whether it needed the cap.
    """
    if not observations:
        raise ValueError("no matched departments to fit against")
    missing = set(complement.EXAMS) - set(sizes)
    if missing:
        raise ValueError(f"missing observed taker counts: {sorted(missing)}")
    exams = sorted(sizes)
    packed = Bars(observations, exams)
    count = segments + 1
    cohort = complement.cohort_size(sizes, overlap)
    guess = np.concatenate([complement.start(count), np.full(len(loadings), 0.9)])

    got = optimize.minimize(
        lambda p: cost(packed, build(p, count, sizes, loadings, nodes)),
        guess,
        method="SLSQP",
        bounds=complement.bounds(count, cohort, sizes)
        + [(floor, CEILING)] * len(loadings),
        constraints=complement.constraints(count, sizes, cohort, nested),
        options={"maxiter": steps, "ftol": 1e-10},
    )
    pool = build(got.x, count, sizes, loadings, nodes)
    pool.cohort = cohort
    pool.degrees = complement.degrees(segments) + len(loadings)
    pool.converged = bool(got.success)
    return pool, disagreement(pool, observations, exams)


Loaded = collections.namedtuple("Loaded", "groups sizes rows cohort")


def load():
    """Every bar the fit compares, with the rows and cohort behind them."""
    import ceec_score
    from lib.paths import data_path
    from pool import bars, fit as pool_fit

    rows, _, _ = pool_fit.source_rows()
    pool_fit.attach_apply_tops(rows)
    cohort = ceec_score.CohortPercentiles.load(data_path("ceec-scores.tsv"))
    groups = bars.observations(rows, pool_fit.exam_of, pool_fit.top_of, cohort)
    return Loaded(groups, pool_fit.taker_counts(), rows, cohort)


def report(pool, observations, error):
    """Print the loadings and where a bar on each measurement now lands."""
    from pool import bars

    print(f"\nfit on {len(observations)} bar pairs")
    print("  " + ", ".join(f"{left}-{right}: {count}" for (left, right), count
                           in sorted(bars.counts(observations).items())))
    print(f"  disagreement: {error:.2f} cohort percentile points")
    print(f"  converged: {pool.converged}, {pool.degrees} parameters")

    print("\nhow sharply each measurement reads ability")
    for measure in sorted(pool.loadings):
        loading = pool.loadings[measure]
        print(f"  {measure:<8}λ = {loading:.3f}   ability explained {loading ** 2:.1%}")

    print("\nwhere the top of each exam's takers lands on the cohort")
    exams = pool.exams
    print("  " + f"{'top of takers':<20}" + "".join(f"{e:>12}" for e in exams))
    for top in (0.01, 0.05, 0.10, 0.25, 0.50):
        cells = "".join(f"{100 * pool.implied_top(e, [top])[0]:>11.1f}%" for e in exams)
        print("  " + f"top {100 * top:>4.0f}% of takers".ljust(20) + cells)


def main():
    from pool import bars, fit as pool_fit

    got = load()
    observations = bars.flatten(got.groups)
    pool, error = fit(observations, got.sizes, pool_fit.BENDS)
    report(pool, observations, error)


if __name__ == "__main__":
    main()
