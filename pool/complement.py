"""Tie 學測 and 統測 together so the picture cannot slide along the ability axis.

Matched thresholds only say where one exam's bar sits relative to another's.
Warping every density the same way leaves every one of those comparisons intact,
so independent densities leave the whole picture free to slide and the fit
settles wherever the spline family happens to bend most cheaply.

Ability here is a percentile inside everyone who sat 學測 or 統測, so it is
uniform over that cohort by construction, and each student sits one exam or the
other. Their two densities therefore add up to the cohort at every ability.
Fitting the 學測 share of the cohort instead of two free densities builds that
in, which is what pins the placement. 指考 draws again from students who
already sat 學測, so it keeps a density of its own.
"""

import numpy as np
from scipy import optimize

from pool import model

ACADEMIC = "gsat"
VOCATIONAL = "tongce"
RETAKE = "zhikao"
EXAMS = (ACADEMIC, RETAKE, VOCATIONAL)


class ComplementPool(model.LinearAbilityPool):
    """學測 and 統測 read off one cohort share, alongside a free 指考."""

    def __init__(self, share, retake, sizes):
        share = np.asarray(share, dtype=float)
        cohort = model.cohort_size(sizes)
        super().__init__(
            {
                ACADEMIC: cohort * share / sizes[ACADEMIC],
                VOCATIONAL: cohort * (1.0 - share) / sizes[VOCATIONAL],
                RETAKE: np.asarray(retake, dtype=float),
            },
            sizes,
        )
        self.share = share

    def cohort_density(self):
        """People per unit ability in 學測 and 統測 together, which is flat."""
        cohort = model.cohort_size(self.sizes)
        return np.full_like(self.share, cohort)


def degrees(segments, zero_tail):
    """Free parameters left after the two normalisations and any zero tail."""
    if segments < 1:
        raise ValueError("a linear density needs at least one segment")
    return 2 * segments - bool(zero_tail)


def trapezoid_weights(nodes):
    """Node weights whose dot product with ordinates is `segments` times a mean."""
    weights = np.ones(nodes)
    weights[[0, -1]] = 0.5
    return weights


def _pack(params, nodes):
    """Split the optimiser vector into the share and 指考 ordinates."""
    return params[:nodes], params[nodes:]


def _constraints(nodes, sizes, zero_tail, monotone, nested):
    """Normalisations, plus whichever shape hypotheses the candidate asserts."""
    segments = nodes - 1
    cohort = model.cohort_size(sizes)
    weights = trapezoid_weights(nodes)
    out = [
        {"type": "eq",
         "fun": lambda p: np.dot(p[:nodes], weights) - segments * sizes[ACADEMIC] / cohort},
        {"type": "eq", "fun": lambda p: np.dot(p[nodes:], weights) - segments},
    ]
    if zero_tail:
        out.append({"type": "eq", "fun": lambda p: p[-1]})
    if monotone:
        out.append({"type": "ineq", "fun": lambda p: np.diff(p[:nodes])})
    if nested:
        # 指考 is a second sitting for students who already took 學測, so it
        # cannot hold more people at an ability than 學測 does.
        out.append({"type": "ineq",
                    "fun": lambda p: cohort * p[:nodes] - sizes[RETAKE] * p[nodes:]})
    return out


def _start(nodes, sizes, zero_tail):
    """A flat share at the observed academic fraction, with a flat 指考."""
    segments = nodes - 1
    share = np.full(nodes, sizes[ACADEMIC] / model.cohort_size(sizes))
    if zero_tail:
        retake = np.full(nodes, segments / (segments - 0.5))
        retake[-1] = 0.0
    else:
        retake = np.ones(nodes)
    return np.concatenate([share, retake])


def fit(observations, sizes, segments, zero_tail=False, monotone=False,
        nested=False, curvature=0.0):
    """Fit the cohort share and the 指考 density, and return (pool, MAE)."""
    if not observations:
        raise ValueError("no matched departments to fit against")
    missing = set(EXAMS) - set(sizes)
    if missing:
        raise ValueError(f"missing observed taker counts: {sorted(missing)}")
    nodes = segments + 1
    pairs = model.Pairs(observations, EXAMS, segments, sizes)
    cap = model.cohort_size(sizes) / sizes[RETAKE]

    def cost(params):
        share, retake = _pack(params, nodes)
        gaps = pairs.gaps(ComplementPool(share, retake, sizes))
        loss = float((pairs.weights * gaps * gaps).sum()) / pairs.weight_sum
        if curvature and segments > 1:
            loss += curvature * float((np.diff(share, n=2) ** 2).sum()
                                      + (np.diff(retake, n=2) ** 2).sum())
        return loss

    got = optimize.minimize(
        cost,
        _start(nodes, sizes, zero_tail),
        method="SLSQP",
        bounds=[(0.0, 1.0)] * nodes + [(0.0, cap)] * nodes,
        constraints=_constraints(nodes, sizes, zero_tail, monotone, nested),
        options={"maxiter": 400, "ftol": 1e-11},
    )
    if not got.success:
        raise RuntimeError(f"complement fit failed: {got.message}")
    pool = ComplementPool(*_pack(got.x, nodes), sizes)
    pool.degrees = degrees(segments, zero_tail)
    return pool, model.residual(pool, observations)
