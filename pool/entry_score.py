"""What a 基北區 entry cutoff says about the student standing at it.

The district ranks its applicants on a 36-point score, but the only national
figures are the shares at each subject mark and the counts in each five-subject
A/B/C category. One latent ability behind five noisy subject readings explains
both: the marks fix where each subject changes grade, and a single correlation
between ability and a subject reading decides how often the five agree, which
is exactly what the category counts measure.

Fitting that correlation gives the whole score distribution, so a cutoff of 33.8
becomes a share of the national cohort and, through the normal the ability was
drawn from, a standing on an ability scale.
"""

import collections
import re
import sys

if __package__ in (None, ""):
    import _bootstrap  # noqa: F401

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import norm

from lib import tsvio
from lib.cap import (GRADE_POINTS, GRADES, MARK_POINTS, MARKS, SUBJECTS,
                     WRITING_POINTS, category_of)
from lib.paths import data_path

NODES = 60
YEAR = "107"
OUTPUT = "cap-entry-scores.tsv"
# Below this the subjects barely agree and above it they are one exam.
BOUNDS = (0.05, 0.995)


def quadrature(count=NODES):
    """Ability nodes and their weights for integrating a standard normal."""
    nodes, weights = np.polynomial.hermite_e.hermegauss(count)
    return nodes, weights / weights.sum()


def mark_edges(rows):
    """Where a standard-normal subject reading changes mark, per subject."""
    shares = collections.defaultdict(dict)
    for row in rows:
        shares[row["subject"]][row["mark"]] = float(row["pct"]) / 100
    out = {}
    for subject, marks in shares.items():
        running, edges = 0.0, []
        for mark in MARKS[:-1]:
            running += marks[mark]
            edges.append(float(norm.ppf(1 - running)))
        out[subject] = edges
    return [out[subject] for subject in SUBJECTS]


def mark_probabilities(edges, nodes, rho):
    """Chance of each mark at every ability node, for one subject."""
    spread = (1 - rho ** 2) ** 0.5
    above = norm.sf((np.array(edges)[:, None] - rho * nodes[None, :]) / spread)
    floor, ceiling = np.zeros(len(nodes)), np.ones(len(nodes))
    return np.diff(np.vstack([floor, above, ceiling]), axis=0)


def joint(edges, nodes, rho):
    """Chance of each (points, A count, B count) at every ability node."""
    state = {(0, 0, 0): np.ones(len(nodes))}
    for subject_edges in edges:
        probabilities = mark_probabilities(subject_edges, nodes, rho)
        moved = collections.defaultdict(lambda: np.zeros(len(nodes)))
        for (points, a_count, b_count), weight in state.items():
            for mark, chance in zip(MARKS, probabilities):
                grade = GRADES[mark]
                key = (points + MARK_POINTS[mark],
                       a_count + (grade == "A"), b_count + (grade == "B"))
                moved[key] = moved[key] + weight * chance
        state = moved
    return state


def population(edges, rho, nodes, weights):
    """The same table with ability integrated out."""
    return {key: float(value @ weights) for key, value in joint(edges, nodes, rho).items()}


def category_shares(table):
    """Collapse a fitted table onto the published five-subject categories."""
    out = collections.defaultdict(float)
    for (_, a_count, b_count), share in table.items():
        out[category_of(a_count, b_count)] += share
    return out


def deviance(observed, predicted):
    """Multinomial deviance of the fitted category shares against the counts."""
    total = sum(observed.values())
    error = 0.0
    for name, count in observed.items():
        share = max(predicted.get(name, 0.0), 1e-12)
        if count:
            error += 2 * count * np.log(count / (total * share))
    return float(error)


def fit(edges, observed, nodes, weights):
    """The one correlation that makes the five subjects agree as often as seen."""
    def cost(rho):
        return deviance(observed, category_shares(population(edges, rho, nodes, weights)))
    found = minimize_scalar(cost, bounds=BOUNDS, method="bounded",
                            options={"xatol": 1e-4})
    return float(found.x), found.fun


def grade_scores(rows):
    """Where a district's coarse 會考 total falls in the national cohort.

    Scoring the three achievement levels and nothing finer makes the total a
    function of the published category alone, so the counts give its
    distribution outright with no model in between.
    """
    counts = collections.defaultdict(float)
    for row in rows:
        marks = re.findall(r"(\d+)([ABC])", row["category"])
        score = sum(int(number) * GRADE_POINTS[grade] for number, grade in marks)
        counts[score] += float(row["students"])
    total = sum(counts.values())
    return {score: counts[score] / total for score in counts}


def writing_shares(rows):
    """Chance of each 寫作 level inside each five-subject category."""
    counts = collections.defaultdict(dict)
    for row in rows:
        counts[row["category"]][row["writing"]] = float(row["students"])
    out = {}
    for category, levels in counts.items():
        total = sum(levels.values())
        out[category] = ({level: count / total for level, count in levels.items()}
                         if total else {})
    return out


def score_shares(table, writing):
    """Chance of each published 36-point score."""
    out = collections.defaultdict(float)
    for (points, a_count, b_count), share in table.items():
        levels = writing.get(category_of(a_count, b_count))
        if not levels:
            continue
        for level, chance in levels.items():
            out[round(points + WRITING_POINTS[level], 1)] += share * chance
    return out


def rows_for(shares, takers):
    """One row per score, carrying the share of the cohort it beats."""
    out, above = [], 0.0
    for score in sorted(shares, reverse=True):
        share = shares[score]
        above += share
        out.append({
            "year": YEAR,
            "score": f"{score:.1f}",
            "students": round(share * takers),
            "pct": round(100 * share, 4),
            "pct_at_or_above": round(100 * above, 4),
        })
    return out


def load():
    """Fitted score table, the correlation behind it, and how well it fits."""
    marks = list(tsvio.read_rows(data_path("cap-subject-marks.tsv")))
    observed = {row["category"]: float(row["students"])
                for row in tsvio.read_rows(data_path("cap-grade-distributions.tsv"))}
    writing = writing_shares(tsvio.read_rows(data_path("cap-writing-levels.tsv")))
    nodes, weights = quadrature()
    edges = mark_edges(marks)
    rho, error = fit(edges, observed, nodes, weights)
    table = population(edges, rho, nodes, weights)
    return {
        "rho": rho,
        "deviance": error,
        "takers": sum(observed.values()),
        "categories": (observed, category_shares(table)),
        "scores": score_shares(table, writing),
    }


def report(fitted, out=sys.stderr):
    observed, predicted = fitted["categories"]
    total = sum(observed.values())
    worst = max(observed, key=lambda name: abs(observed[name] / total - predicted[name]))
    print(f"subject correlation with ability {fitted['rho']:.3f};"
          f" category deviance {fitted['deviance']:,.0f} over {total:,.0f} takers",
          file=out)
    print(f"worst category {worst}: {100 * observed[worst] / total:.2f}% observed,"
          f" {100 * predicted[worst]:.2f}% fitted", file=out)


def main():
    fitted = load()
    report(fitted)
    rows = rows_for(fitted["scores"], fitted["takers"])
    written = tsvio.write_rows(data_path(OUTPUT), rows)
    print(f"wrote {written} rows to {data_path(OUTPUT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
