"""Compare candidate test-pool density models on held-out departments.

Matched thresholds only say where one exam's bar sits relative to another's, and
warping every density the same way leaves all of those comparisons intact. Three
independent densities are therefore free to slide along the ability axis
together, so training error alone cannot rank these models: extra bends buy
error that describes the spline family rather than the cohort. Everything here
is judged on departments the fit never saw.

The candidates differ in three ways: whether 學測 and 統測 are tied to the
cohort they partition, how many bends each density gets, and whether 指考 is
made to vanish at the top of the ability range.
"""

import argparse
import collections
import math
import time

import numpy as np

from pool import complement
from pool import fit as pool_fit
from pool import model


def independent(segments, **hypotheses):
    """Fit each exam its own density, normalised but otherwise unconstrained."""
    def run(observations, exams, sizes):
        return model.fit_linear(observations, exams, sizes, segments,
                                require_unimodal=False, **hypotheses)
    return run


def tied(segments, **hypotheses):
    """Fit 學測's share of the cohort, so 統測 is whatever is left over."""
    def run(observations, exams, sizes):
        return complement.fit(observations, sizes, segments, **hypotheses)
    return run


COVER = ("gsat", "tongce")

CANDIDATES = (
    ("free densities, 2 bends, 指考 tail zero", independent(2, zero_tails=("zhikao",))),
    ("free densities, 3 bends, 指考 tail zero", independent(3, zero_tails=("zhikao",))),
    ("free densities, 3 bends", independent(3)),
    ("free densities, 3 bends, cohort covered on top", independent(3, top_floor=COVER)),
    ("free densities, 4 bends, cohort covered on top", independent(4, top_floor=COVER)),
    ("tied to cohort, 1 bend", tied(1)),
    ("tied to cohort, 2 bends", tied(2)),
    ("tied to cohort, 3 bends", tied(3)),
    ("tied to cohort, 4 bends", tied(4)),
    ("tied to cohort, 5 bends", tied(5)),
    ("tied to cohort, 3 bends, 指考 tail zero", tied(3, zero_tail=True)),
    ("tied to cohort, 3 bends, share rises", tied(3, monotone=True)),
    ("tied to cohort, 3 bends, 指考 under 學測", tied(3, nested=True)),
)


def observations_by_department(rows):
    """Return only groups with at least one cross-exam threshold pair."""
    return model.matched_groups(rows, pool_fit.exam_of, pool_fit.top_of)


def flatten(groups):
    """Flatten a sequence of ``(department, observations)`` pairs."""
    return [pair for _, pairs in groups for pair in pairs]


def fit_candidate(observations, exams, sizes, candidate):
    """Fit one candidate and return the pool, its errors, and its elapsed time."""
    started = time.perf_counter()
    fitted, mae = candidate[1](observations, exams, sizes)
    return (fitted, mae, model.squared_error(fitted, observations),
            time.perf_counter() - started)


def weighted_mean(measures):
    """Average values supplied as ``(value, weight)`` pairs."""
    total = sum(weight for _, weight in measures)
    return sum(value * weight for value, weight in measures) / total


def balanced_folds(groups, count):
    """Place whole departments in folds with approximately equal seat weight."""
    folds = [[] for _ in range(count)]
    totals = [0.0] * count
    for group in sorted(groups, key=lambda item: -sum(p[4] for p in item[1])):
        index = min(range(count), key=totals.__getitem__)
        folds[index].append(group)
        totals[index] += sum(pair[4] for pair in group[1])
    return folds


def cross_validate(groups, exams, sizes, folds, candidates):
    """Held-out error per candidate, plus its spread over the folds."""
    held_out = collections.defaultdict(list)
    for index, test_groups in enumerate(folds):
        train = flatten(g for i, fold in enumerate(folds) if i != index for g in fold)
        test = flatten(test_groups)
        weight = sum(pair[4] for pair in test)
        for candidate in candidates:
            try:
                fitted, _, _, _ = fit_candidate(train, exams, sizes, candidate)
            except RuntimeError:
                continue
            held_out[candidate[0]].append((model.residual(fitted, test), weight))
    return {
        name: (weighted_mean(measures), float(np.std([m for m, _ in measures])))
        for name, measures in held_out.items()
    }


def out_of_bag(groups, exams, sizes, candidates, resamples, seed=20260809):
    """Paired held-out error over bootstrap resamples of whole departments.

    Every candidate sees the same resample, so the differences between them are
    paired and the department-to-department noise they share cancels. A resample
    where any candidate fails to converge is dropped whole, keeping that pairing.
    """
    rng = np.random.default_rng(seed)
    scores = collections.defaultdict(list)
    for _ in range(resamples):
        drawn = rng.integers(0, len(groups), len(groups))
        train = flatten(groups[i] for i in drawn)
        test = flatten(groups[i] for i in
                       sorted(set(range(len(groups))) - set(drawn.tolist())))
        if not test:
            continue
        try:
            got = [model.residual(fit_candidate(train, exams, sizes, c)[0], test)
                   for c in candidates]
        except RuntimeError:
            continue
        for candidate, error in zip(candidates, got):
            scores[candidate[0]].append(error)
    return scores


def bic_delta(mse, degrees, reference_mse, reference_degrees, observations):
    """Gaussian BIC difference, using independent GSAT–統測 pairs conservatively."""
    return (observations * math.log(mse / reference_mse)
            + (degrees - reference_degrees) * math.log(observations))


def report_full_fits(observations, exams, sizes, bottleneck, candidates):
    """Fit every candidate on everything, which ranks them mostly by flexibility."""
    results = []
    for candidate in candidates:
        try:
            fitted, mae, mse, elapsed = fit_candidate(observations, exams, sizes,
                                                      candidate)
        except RuntimeError as failure:
            print(f"{candidate[0]:<42} {failure}")
            continue
        results.append((candidate, fitted.degrees, mae, mse, elapsed))
    reference = results[0]
    print(f"\n{'model':<42}{'dof':>4}{'MAE':>8}{'MSE':>10}{'sec':>7}{'BIC Δ':>8}")
    for candidate, degrees, mae, mse, elapsed in results:
        delta = bic_delta(mse, degrees, reference[3], reference[1], bottleneck)
        print(f"{candidate[0]:<42}{degrees:>4}{mae:>8.2f}{mse:>10.2f}"
              f"{elapsed:>7.2f}{delta:>8.1f}")
    return results


def report_held_out(groups, exams, sizes, fold_count, candidates):
    """Rank the candidates on departments their fit never saw."""
    print(f"\n{fold_count}-fold held-out error, departments kept whole")
    scored = cross_validate(groups, exams, sizes,
                            balanced_folds(groups, fold_count), candidates)
    order = sorted(scored, key=lambda name: scored[name][0])
    print(f"{'model':<42}{'MAE':>8}{'fold sd':>10}")
    for name in order:
        mae, spread = scored[name]
        print(f"{name:<42}{mae:>8.2f}{spread:>10.2f}")
    return order


def report_bootstrap(groups, exams, sizes, finalists, resamples):
    """Say whether the leader's margin survives resampling the departments."""
    print(f"\n{resamples} bootstrap resamples, scored on the departments left out")
    scores = out_of_bag(groups, exams, sizes, finalists, resamples)
    best = min(scores, key=lambda name: float(np.mean(scores[name])))
    reference = np.array(scores[best])
    print(f"{'model':<42}{'MAE':>8}{'vs best':>10}{'wins':>8}")
    for candidate in finalists:
        errors = np.array(scores[candidate[0]])
        gap = errors - reference
        wins = float((gap < 0).mean()) if candidate[0] != best else float("nan")
        marker = "  <- best" if candidate[0] == best else ""
        print(f"{candidate[0]:<42}{errors.mean():>8.2f}{gap.mean():>+10.2f}"
              f"{wins:>8.2f}{marker}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folds", type=int, default=5,
                        help="grouped cross-validation folds; 0 to skip")
    parser.add_argument("--bootstrap", type=int, default=0,
                        help="paired bootstrap resamples over the top candidates")
    parser.add_argument("--finalists", type=int, default=3,
                        help="how many held-out leaders the bootstrap compares")
    parser.add_argument("--only", default="",
                        help="keep only candidates whose name contains this")
    args = parser.parse_args()
    candidates = tuple(c for c in CANDIDATES if args.only in c[0])
    rows, _ = pool_fit.observations()
    groups = observations_by_department(rows)
    observations = flatten(groups)
    exams = sorted({exam for row in observations for exam in (row[0], row[2])})
    sizes = pool_fit.taker_counts()
    bottleneck = sum({left, right} == {"gsat", "tongce"}
                     for left, _, right, _, _ in observations)
    print(f"{len(observations)} pairs in {len(groups)} department groups")
    print(f"using {bottleneck} GSAT–統測 pairs as the conservative BIC n")
    report_full_fits(observations, exams, sizes, bottleneck, candidates)
    if not args.folds:
        return
    order = report_held_out(groups, exams, sizes, args.folds, candidates)
    if args.bootstrap:
        best = [c for c in candidates if c[0] in order[: args.finalists]]
        report_bootstrap(groups, exams, sizes, best, args.bootstrap)


if __name__ == "__main__":
    main()
