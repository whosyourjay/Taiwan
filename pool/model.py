"""Put every exam's takers on one ability axis so their percentiles compare.

A percentile inside one exam's takers says nothing next to another's. Each exam
draws its own unknown population from the original cohort, and a student may sit
any subset of the exams. Ranking first in one is not ranking first in another.

Model each exam's takers as a density over ability, where ability is the
percentile in the whole cohort and so is uniform by construction. The density
can be piecewise constant or continuous piecewise linear. The top `p` of an
exam's takers are those above the ability where its own cumulative, counted
from the top, reaches `p`.

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
    """Independent exam PDFs across equal-width bins of cohort ability.

    `shares[exam]` sums to 1 over bins ordered from lowest ability to highest.
    Multiplying it by `sizes[exam]` makes its integral equal the observed number
    of students who took that exam.
    """

    def __init__(self, shares, bins, sizes=None):
        self.shares = {e: np.asarray(s, dtype=float) for e, s in shares.items()}
        self.exams = sorted(self.shares)
        self.bins = bins
        self.sizes = {e: float((sizes or {}).get(e, 1.0)) for e in self.shares}

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

    def bin_counts(self, exam):
        """Fitted number of this exam's takers in each ability bin."""
        return self.shares[exam] * self.sizes[exam]

    def density(self, exam):
        """Takers per unit cohort fraction; its integral is the exam size."""
        return self.bin_counts(exam) * self.bins

    def percentile_density(self, exam):
        """Takers per one cohort-percentile point, on an axis from 0 to 100."""
        return self.density(exam) / 100.0


class LinearAbilityPool:
    """Independent piecewise-linear PDFs with equally spaced breakpoints.

    `values` gives a probability density at each breakpoint. Its trapezoidal
    integral is one, so multiplying by the exam's observed taker count gives a
    density of people. Linear interpolation keeps the rank conversion smooth.
    """

    def __init__(self, values, sizes):
        self.values = {
            exam: np.asarray(value, dtype=float) for exam, value in values.items()
        }
        self.exams = sorted(self.values)
        self.bins = len(next(iter(self.values.values()))) - 1
        self.sizes = {exam: float(sizes[exam]) for exam in self.exams}

    def masses(self, exam):
        """Taker shares inside each linear segment, from low to high ability."""
        value = self.values[exam]
        return (value[:-1] + value[1:]) / (2 * self.bins)

    def abilities(self, exam, top_fractions):
        """Cohort percentile of each within-exam top fraction."""
        values = self.values[exam]
        width = 1.0 / self.bins
        above = np.concatenate([np.cumsum(self.masses(exam)[::-1])[::-1], [0.0]])
        tops = np.clip(np.asarray(top_fractions, dtype=float), 0.0, 1.0)
        segment = self.bins - np.searchsorted(above[::-1], tops, side="left")
        segment = np.clip(segment, 0, self.bins - 1)
        needed = tops - above[segment + 1]
        left, right = values[segment], values[segment + 1]
        slope = (right - left) / width
        radical = np.maximum(right * right - 2 * slope * needed, 0.0)
        denominator = right + np.sqrt(radical)
        back = np.divide(2 * needed, denominator, out=np.zeros_like(needed),
                         where=denominator != 0)
        return (segment + 1) * width - back

    def ability(self, exam, top_fraction):
        """Cohort percentile of one within-exam top fraction."""
        return float(self.abilities(exam, [top_fraction])[0])

    def bin_counts(self, exam):
        """Fitted taker counts in each linear segment."""
        return self.masses(exam) * self.sizes[exam]

    def percentile_density_points(self, exam):
        """Density at every breakpoint, in takers per cohort-percentile point."""
        return self.values[exam] * self.sizes[exam] / 100.0


def _shares_from(params, exams, bins):
    """Softmax each exam's free parameters into positive shares summing to 1."""
    out = {}
    for i, exam in enumerate(exams):
        raw = params[i * bins:(i + 1) * bins]
        raw = raw - raw.max()
        weights = np.exp(raw)
        out[exam] = weights / weights.sum()
    return out


class Pairs:
    """Observations packed into arrays so a cost evaluation is a few vector ops."""

    def __init__(self, observations, exams, bins, sizes=None):
        index = {e: i for i, e in enumerate(exams)}
        self.exams = list(exams)
        self.bins = bins
        self.sizes = sizes
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
                       problem.bins, problem.sizes)
    gaps = problem.gaps(pool)
    cost = float((problem.weights * gaps * gaps).sum()) / problem.weight_sum
    # Without this the fit is free to spike one bin, which fits a few matched
    # departments and says nothing about the cohort.
    for exam in problem.exams:
        steps = np.diff(pool.shares[exam])
        cost += smooth * float((steps * steps).sum())
    return cost


def fit(observations, exams, sizes, bins=3, smooth=0.05, restarts=6,
        seed=20260809):
    """Fit per-exam bin shares so matched departments agree on ability.

    `observations` are (exam_a, top_a, exam_b, top_b, weight), each a department
    admitting through two exams, with the share of each exam's takers that
    cleared its bar. `sizes` fixes each independent PDF's integral. Returns
    (pool, mean_abs_disagreement).
    """
    if not observations:
        raise ValueError("no matched departments to fit against")
    missing = set(exams) - set(sizes)
    if missing:
        raise ValueError(f"missing observed taker counts: {sorted(missing)}")
    problem = Pairs(observations, exams, bins, sizes)
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
    pool = AbilityPool(_shares_from(best.x, exams, bins), bins, sizes)
    return pool, residual(pool, observations)


RETAKE = "zhikao"


def covering(sizes):
    """Exams whose takers make up the cohort; 指考 only sits students again."""
    return [exam for exam in sorted(sizes) if exam != RETAKE]


def cohort_size(sizes):
    """Original cohort: the academic and vocational test-taking populations."""
    return float(sum(sizes[exam] for exam in covering(sizes)))


def linear_degrees(exams, segments, zero_tails=()):
    """Number of free ordinates in normalized linear-spline densities."""
    if segments < 1:
        raise ValueError("a linear density needs at least one segment")
    tails = set(zero_tails)
    unknown = tails - set(exams)
    if unknown:
        raise ValueError(f"zero-tail exams are not fitted: {sorted(unknown)}")
    return segments * len(exams) - len(tails)


def _linear_values(params, exams, segments):
    """Unpack a flat optimizer vector into each exam's spline ordinates."""
    nodes = segments + 1
    return {
        exam: np.asarray(params[i * nodes:(i + 1) * nodes])
        for i, exam in enumerate(exams)
    }


def is_unimodal(values):
    """Whether values rise then fall, allowing either endpoint as the peak."""
    for peak in range(len(values)):
        if (np.all(np.diff(values[:peak + 1]) >= -1e-9)
                and np.all(np.diff(values[peak:]) <= 1e-9)):
            return True
    return False


def _linear_problem(observations, exams, sizes, segments, zero_tails, curvature,
                    top_floor=()):
    """Pack a bounded linear-spline fit into an SLSQP objective."""
    problem = Pairs(observations, exams, segments, sizes)
    cap = {exam: cohort_size(sizes) / sizes[exam] for exam in exams}
    nodes = segments + 1
    bounds, start, constraints = [], [], []
    tops = []
    weights = np.ones(nodes)
    weights[[0, -1]] = 0.5
    for exam in exams:
        bounds.extend([(0.0, cap[exam])] * nodes)
        if exam in zero_tails:
            start.extend([segments / (segments - 0.5)] * (nodes - 1) + [0.0])
        else:
            start.extend([1.0] * nodes)
        offset = len(start) - nodes
        constraints.append({
            "type": "eq",
            "fun": lambda p, o=offset: np.dot(p[o:o + nodes], weights) - segments,
        })
        if exam in zero_tails:
            constraints.append({
                "type": "eq", "fun": lambda p, o=offset: p[o + nodes - 1],
            })
        if exam in top_floor:
            tops.append((offset + nodes - 1, sizes[exam]))
    if tops:
        # Nobody at the very top of the cohort skips every exam, so the named
        # exams have to account for the whole cohort there between them.
        floor = cohort_size(sizes)
        constraints.append({
            "type": "ineq",
            "fun": lambda p: sum(size * p[i] for i, size in tops) - floor,
        })

    def cost(params):
        values = _linear_values(params, exams, segments)
        pool = LinearAbilityPool(values, sizes)
        gaps = problem.gaps(pool)
        loss = float((problem.weights * gaps * gaps).sum()) / problem.weight_sum
        if curvature:
            loss += curvature * sum(
                float((np.diff(value, n=2) ** 2).sum()) for value in values.values()
            )
        return loss

    return cost, bounds, constraints, start


def fit_linear(observations, exams, sizes, segments, zero_tails=(), curvature=0.0,
               require_unimodal=True, top_floor=()):
    """Fit capped, continuous linear densities, rejecting non-unimodal output."""
    if not observations:
        raise ValueError("no matched departments to fit against")
    missing = set(exams) - set(sizes)
    if missing:
        raise ValueError(f"missing observed taker counts: {sorted(missing)}")
    tails = frozenset(zero_tails)
    cost, bounds, constraints, start = _linear_problem(
        observations, exams, sizes, segments, tails, curvature, frozenset(top_floor)
    )
    got = optimize.minimize(
        cost,
        np.asarray(start),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 300, "ftol": 1e-10},
    )
    if not got.success:
        raise RuntimeError(f"linear fit failed: {got.message}")
    pool = LinearAbilityPool(_linear_values(got.x, exams, segments), sizes)
    if require_unimodal and not all(is_unimodal(value) for value in pool.values.values()):
        raise RuntimeError("linear fit is not unimodal; choose an explicit peak model")
    pool.degrees = linear_degrees(exams, segments, tails)
    return pool, residual(pool, observations)


def fit_two_line(observations, exams, sizes, require_unimodal=True):
    """Fit two continuous lines per exam, with a zero-density 指考 upper tail.

    This has five shape parameters: two each for 學測 and 統測, and one for
    指考. The last constraint expresses the hypothesis that a student who has
    already aced 學測 skips the second academic exam. 學測 and 統測 tails are
    fitted, never anchored. Density is capped at the original cohort size.
    """
    required = {"gsat", "tongce", "zhikao"}
    if set(exams) != required:
        raise ValueError(f"two-line fit requires exactly {sorted(required)}")
    return fit_linear(
        observations,
        exams,
        sizes,
        2,
        zero_tails=("zhikao",),
        require_unimodal=require_unimodal,
    )


def residual(pool, observations):
    """Seat-weighted mean absolute disagreement, in cohort percentile points."""
    if not observations:
        return 0.0
    exams = sorted({e for o in observations for e in (o[0], o[2])})
    problem = Pairs(observations, exams, pool.bins)
    gaps = np.abs(problem.gaps(pool))
    return 100.0 * float((problem.weights * gaps).sum()) / problem.weight_sum


def squared_error(pool, observations):
    """Seat-weighted squared disagreement, in cohort-percentile-points squared."""
    if not observations:
        return 0.0
    exams = sorted({exam for row in observations for exam in (row[0], row[2])})
    problem = Pairs(observations, exams, pool.bins)
    gaps = problem.gaps(pool)
    return 10_000.0 * float((problem.weights * gaps * gaps).sum()) / problem.weight_sum


def matched_groups(rows, exam_of, top_of, key=None):
    """Build matched observations, retaining their department group keys.

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
    for group, by_exam in groups.items():
        names = sorted(by_exam)
        pairs = []
        for i, exam_a in enumerate(names):
            for exam_b in names[i + 1:]:
                pairs.append((exam_a, _mean(by_exam[exam_a]),
                              exam_b, _mean(by_exam[exam_b]),
                              min(_seats(by_exam[exam_a]), _seats(by_exam[exam_b]))))
        if pairs:
            out.append((group, pairs))
    return out


def matched(rows, exam_of, top_of, key=None):
    """Build all same-department admission-threshold observations."""
    return [pair for _, pairs in matched_groups(rows, exam_of, top_of, key)
            for pair in pairs]


def _mean(pairs):
    seats = sum(n for _, n in pairs)
    return sum(t * n for t, n in pairs) / seats if seats else math.nan


def _seats(pairs):
    return sum(n for _, n in pairs)
