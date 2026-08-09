"""Compare a few defensible test-pool density models.

The models differ only in the 指考 upper-tail hypothesis and in whether each
density receives one extra bend. Cross-validation holds out whole departments,
so several correlated threshold pairs never land on opposite sides of a split.
"""

import argparse
import collections
import math
import time

from pool import fit as pool_fit
from pool import model

CANDIDATES = (
    ("two segments; 指考 tail zero", 2, ("zhikao",)),
    ("two segments; all tails free", 2, ()),
    ("three segments; 指考 tail zero", 3, ("zhikao",)),
)


def observations_by_department(rows):
    """Return only groups with at least one cross-exam threshold pair."""
    return model.matched_groups(rows, pool_fit.exam_of, pool_fit.top_of)


def flatten(groups):
    """Flatten a sequence of ``(department, observations)`` pairs."""
    return [pair for _, pairs in groups for pair in pairs]


def balanced_folds(groups, count):
    """Place whole departments in folds with approximately equal seat weight."""
    folds = [[] for _ in range(count)]
    totals = [0.0] * count
    for group in sorted(groups, key=lambda item: -sum(p[4] for p in item[1])):
        index = min(range(count), key=totals.__getitem__)
        folds[index].append(group)
        totals[index] += sum(pair[4] for pair in group[1])
    return folds


def fit_candidate(observations, exams, sizes, candidate):
    """Fit one candidate and return error metrics with its elapsed time."""
    _, segments, zero_tails = candidate
    started = time.perf_counter()
    fitted, mae = model.fit_linear(
        observations, exams, sizes, segments, zero_tails=zero_tails
    )
    return fitted, mae, model.squared_error(fitted, observations), time.perf_counter() - started


def weighted_mean(measures):
    """Average values supplied as ``(value, weight)`` pairs."""
    total = sum(weight for _, weight in measures)
    return sum(value * weight for value, weight in measures) / total


def cross_validate(groups, exams, sizes, folds):
    """Compute seat-weighted held-out error for each non-redundant candidate."""
    held_out = collections.defaultdict(list)
    for index, test_groups in enumerate(folds):
        train = flatten(group for i, fold in enumerate(folds) if i != index for group in fold)
        test = flatten(test_groups)
        weight = sum(pair[4] for pair in test)
        for candidate in (CANDIDATES[0], CANDIDATES[2]):
            fitted, _, _, _ = fit_candidate(train, exams, sizes, candidate)
            held_out[candidate[0]].append((
                model.residual(fitted, test), model.squared_error(fitted, test), weight
            ))
    return {
        name: (
            weighted_mean((mae, weight) for mae, _, weight in measures),
            weighted_mean((mse, weight) for _, mse, weight in measures),
        )
        for name, measures in held_out.items()
    }


def bic_delta(mse, degrees, reference_mse, reference_degrees, observations):
    """Gaussian BIC difference, using independent GSAT–統測 pairs conservatively."""
    return (observations * math.log(mse / reference_mse)
            + (degrees - reference_degrees) * math.log(observations))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--folds", type=int, default=0,
                        help="run this many grouped cross-validation folds")
    args = parser.parse_args()
    rows, _ = pool_fit.observations()
    groups = observations_by_department(rows)
    observations = flatten(groups)
    exams = sorted({exam for row in observations for exam in (row[0], row[2])})
    sizes = pool_fit.taker_counts()
    bottleneck = sum({left, right} == {"gsat", "tongce"}
                     for left, _, right, _, _ in observations)
    print(f"{len(observations)} pairs in {len(groups)} department groups")
    print(f"using {bottleneck} GSAT–統測 pairs as the conservative BIC n")
    results = []
    for candidate in CANDIDATES:
        fitted, mae, mse, elapsed = fit_candidate(observations, exams, sizes, candidate)
        results.append((candidate, fitted.degrees, mae, mse, elapsed))
    reference = results[0]
    print("\n" + "model".ljust(42) + "dof     MAE       MSE     fit seconds  BIC Δ")
    for candidate, degrees, mae, mse, elapsed in results:
        delta = bic_delta(mse, degrees, reference[3], reference[1], bottleneck)
        print(f"{candidate[0]:<42}{degrees:>3}  {mae:>7.2f}  {mse:>8.2f}"
              f"  {elapsed:>12.3f}  {delta:>5.1f}")
    if args.folds:
        print(f"\n{args.folds}-fold department-grouped validation")
        results = cross_validate(groups, exams, sizes, balanced_folds(groups, args.folds))
        for name, (mae, mse) in results.items():
            print(f"{name}: held-out MAE {mae:.2f}, MSE {mse:.2f}")


if __name__ == "__main__":
    main()
