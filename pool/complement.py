"""Stop the fitted densities sliding along the ability axis.

Matched thresholds only say where one exam's bar sits relative to another's.
Warping every density the same way leaves all of those comparisons intact, so
free densities slide: they put 學測 and 統測 together at twice the cohort in
mid-range and at nothing near the bottom, which no population can do.

Counting people rules that out. Ability is a percentile inside the cohort, so
the cohort's density along it is flat. Three facts then bound the fit. Nobody at
one ability can be more of the cohort than all of it, which caps each exam.
Every student sits 學測 or 統測, which puts a floor under those two together.
And they double-count only the students who sit both, so the two taker counts
added up exceed the cohort by exactly that overlap, which is all the room the
floor leaves.

The cohort here is whoever sat at least one of the two, so students who sat
neither are outside it rather than unaccounted for.
"""

import numpy as np
from scipy import optimize

from pool import model

ACADEMIC = "gsat"
VOCATIONAL = "tongce"
RETAKE = "zhikao"
EXAMS = (ACADEMIC, RETAKE, VOCATIONAL)
COVER = (ACADEMIC, VOCATIONAL)


def cohort_size(sizes, overlap):
    """Students who sat 學測 or 統測, counting those who sat both once.

    `overlap` is how many sat both, as a share of that cohort.
    """
    if overlap < 0:
        raise ValueError("overlap is a share of the cohort, so it cannot be negative")
    return sum(sizes[exam] for exam in COVER) / (1.0 + overlap)


def degrees(segments):
    """Free ordinates left once each density is normalised."""
    if segments < 1:
        raise ValueError("a linear density needs at least one segment")
    return 3 * segments


def trapezoid_weights(nodes):
    """Node weights whose dot product with ordinates is `segments` times a mean."""
    weights = np.ones(nodes)
    weights[[0, -1]] = 0.5
    return weights


def _values(params, nodes):
    """Split the optimiser vector into each exam's spline ordinates."""
    return {exam: params[i * nodes:(i + 1) * nodes]
            for i, exam in enumerate(EXAMS)}


def _constraints(nodes, sizes, cohort, nested):
    """Normalise each density, then bound how they may stack up on each other.

    A linear function over a segment takes its extremes at the ends, so testing
    every stacking rule at the nodes tests it everywhere.
    """
    segments = nodes - 1
    weights = trapezoid_weights(nodes)
    out = [
        {"type": "eq",
         "fun": lambda p, i=i: np.dot(p[i * nodes:(i + 1) * nodes], weights) - segments}
        for i in range(len(EXAMS))
    ]
    covering = [(EXAMS.index(exam), sizes[exam]) for exam in COVER]
    out.append({
        "type": "ineq",
        "fun": lambda p: sum(size * p[i * nodes:(i + 1) * nodes]
                             for i, size in covering) - cohort,
    })
    if nested:
        # 指考 is a second sitting for students who already took 學測, so it
        # cannot hold more people at an ability than 學測 does.
        academic, retake = EXAMS.index(ACADEMIC), EXAMS.index(RETAKE)
        out.append({
            "type": "ineq",
            "fun": lambda p: (sizes[ACADEMIC] * p[academic * nodes:(academic + 1) * nodes]
                              - sizes[RETAKE] * p[retake * nodes:(retake + 1) * nodes]),
        })
    return out


def fit(observations, sizes, segments, overlap=0.0, nested=True, curvature=0.0):
    """Fit densities that stack up into a possible population, and return (pool, MAE).

    `overlap` is the share of the cohort sitting both 學測 and 統測. At zero the
    floor and the taker counts leave no slack, so the two densities have to add
    up to the cohort exactly; raising it buys the pair room to overlap.
    """
    if not observations:
        raise ValueError("no matched departments to fit against")
    missing = set(EXAMS) - set(sizes)
    if missing:
        raise ValueError(f"missing observed taker counts: {sorted(missing)}")
    nodes = segments + 1
    cohort = cohort_size(sizes, overlap)
    pairs = model.Pairs(observations, EXAMS, segments, sizes)

    def cost(params):
        values = _values(params, nodes)
        gaps = pairs.gaps(model.LinearAbilityPool(values, sizes))
        loss = float((pairs.weights * gaps * gaps).sum()) / pairs.weight_sum
        if curvature and segments > 1:
            loss += curvature * sum(float((np.diff(v, n=2) ** 2).sum())
                                    for v in values.values())
        return loss

    got = optimize.minimize(
        cost,
        np.concatenate([np.full(nodes, 1.0) for _ in EXAMS]),
        method="SLSQP",
        bounds=[(0.0, cohort / sizes[exam]) for exam in EXAMS for _ in range(nodes)],
        constraints=_constraints(nodes, sizes, cohort, nested),
        options={"maxiter": 600, "ftol": 1e-11},
    )
    if not got.success:
        raise RuntimeError(f"complement fit failed: {got.message}")
    pool = model.LinearAbilityPool(_values(got.x, nodes), sizes)
    pool.degrees = degrees(segments)
    pool.cohort = cohort
    return pool, model.residual(pool, observations)


def cover(pool):
    """People in 學測 and 統測 together at each node, over the cohort."""
    total = sum(pool.values[exam] * pool.sizes[exam] for exam in COVER)
    return total / pool.cohort
