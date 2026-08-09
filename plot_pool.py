"""Draw the fitted taker densities and the conversion they imply.

Left: how thickly each exam draws from the cohort, against the flat line an exam
sat by everyone would trace. Right: what a given position inside one exam's
takers is worth on the cohort, which is the left panel integrated.
"""

import os

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (after the backend is fixed)

import fit_pool  # noqa: E402
import pool  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "pool-densities.png")

STYLE = {
    "gsat": ("#1f6feb", "學測 (GSAT)"),
    "zhikao": ("#d1242f", "指考 / 分科測驗"),
    "tongce": ("#1a7f37", "統測"),
}
FONTS = ["PingFang HK", "Heiti TC", "Arial Unicode MS", "Hiragino Sans GB"]


def steps(shares, bins):
    """Density as x, y arrays that draw as a staircase across the bins."""
    x, y = [], []
    for k in range(bins):
        x += [100.0 * k / bins, 100.0 * (k + 1) / bins]
        y += [shares[k] * bins, shares[k] * bins]
    return np.array(x), np.array(y)


def draw(fitted, sizes, observations, error, naive, year, path=OUT):
    plt.rcParams["font.sans-serif"] = FONTS + plt.rcParams["font.sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    figure, (left, right) = plt.subplots(1, 2, figsize=(12.5, 5.2))
    exams = sorted(fitted.shares)

    for exam in exams:
        colour, label = STYLE.get(exam, ("#57606a", exam))
        x, y = steps(fitted.shares[exam], fitted.bins)
        left.plot(x, y, color=colour, linewidth=2.4,
                  label=f"{label}  ({sizes.get(exam, 0):,.0f} takers)")
        left.fill_between(x, 1.0, y, color=colour, alpha=0.13)
    left.axhline(1.0, color="#57606a", linewidth=1.0, linestyle="--")
    left.set_xlim(0, 100)
    left.set_ylim(0, max(1.4, max((fitted.shares[e] * fitted.bins).max()
                                  for e in exams) * 1.18))
    left.set_xlabel("cohort ability percentile  (100 = top)")
    left.set_ylabel("taker density  (1.0 = the exam's fair share)")
    left.set_title(f"Who sits each exam, {year}")
    left.legend(loc="upper left", frameon=False, fontsize=9)
    left.grid(alpha=0.18)

    tops = np.linspace(0.001, 1.0, 400)
    for exam in exams:
        colour, label = STYLE.get(exam, ("#57606a", exam))
        right.plot(100 * tops, 100 * fitted.abilities(exam, tops),
                   color=colour, linewidth=2.4, label=label)
    right.plot([0, 100], [100, 0], color="#57606a", linewidth=1.0,
               linestyle="--", label="if percentiles transferred directly")
    right.set_xlim(0, 100)
    right.set_ylim(0, 100)
    right.set_xlabel("top % of that exam's takers")
    right.set_ylabel("cohort ability percentile")
    right.set_title("What a rank inside one exam is worth")
    right.legend(loc="upper right", frameon=False, fontsize=9)
    right.grid(alpha=0.18)

    figure.suptitle(
        f"Taiwanese admission exams on one cohort axis — "
        f"{len(observations):,} matched departments, "
        f"disagreement {naive:.1f} → {error:.1f} percentile points",
        fontsize=11,
    )
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    return path


def main():
    rows, observations = fit_pool.observations()
    exams = sorted({e for o in observations for e in (o[0], o[2])})
    fitted, error = pool.fit(observations, exams, bins=fit_pool.BINS)
    written = draw(fitted, fit_pool.taker_counts(), observations, error,
                   fit_pool.naive_error(observations), fit_pool.YEAR)
    print(f"wrote {written}")


if __name__ == "__main__":
    main()
