"""Draw the fitted taker densities and the conversion they imply.

Left: the count density for each exam, whose area is its observed number of
takers. 學測 and 統測 are mirror images because every student sits one or the
other, so at each ability they divide the cohort between them; 指考 draws again
from students who already sat 學測 and so overlaps it freely. Right: what a
position inside one exam's takers is worth on the cohort, which is the
corresponding left-panel curve integrated.
"""

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (after the backend is fixed)

from lib.paths import path  # noqa: E402
from pool import model  # noqa: E402

OUT = path("pool-densities.png")

STYLE = {
    "gsat": ("#1f6feb", "學測 (GSAT)"),
    "zhikao": ("#d1242f", "指考 / 分科測驗"),
    "tongce": ("#1a7f37", "統測"),
}
COVER = ("gsat", "tongce")
FONTS = ["PingFang HK", "Heiti TC", "Arial Unicode MS", "Hiragino Sans GB"]


def steps(values, bins):
    """Density as x, y arrays that draw as a staircase across the bins."""
    x, y = [], []
    for k in range(bins):
        x += [100.0 * k / bins, 100.0 * (k + 1) / bins]
        y += [values[k], values[k]]
    return np.array(x), np.array(y)


def density_curve(fitted, exam):
    """Density curve for either constant bins or a continuous linear fit."""
    if hasattr(fitted, "percentile_density_points"):
        values = fitted.percentile_density_points(exam)
        return np.linspace(0.0, 100.0, len(values)), values
    return steps(fitted.percentile_density(exam), fitted.bins)


def draw(fitted, sizes, observations, error, naive, year, path=OUT):
    plt.rcParams["font.sans-serif"] = FONTS + plt.rcParams["font.sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    figure, (left, right) = plt.subplots(1, 2, figsize=(12.5, 5.2))
    exams = fitted.exams

    for exam in exams:
        colour, label = STYLE.get(exam, ("#57606a", exam))
        x, y = density_curve(fitted, exam)
        left.plot(x, y, color=colour, linewidth=2.4,
                  label=f"{label}  ({sizes.get(exam, 0):,.0f} takers)")
        left.fill_between(x, 0.0, y, color=colour, alpha=0.13)
    cohort = sum(sizes.get(exam, 0) for exam in COVER) / 100.0
    if cohort:
        left.axhline(cohort, color="#57606a", linewidth=1.0, linestyle="--",
                     label="學測 + 統測, the whole cohort")
    left.set_xlim(0, 100)
    left.set_ylim(0, max([cohort] + [density_curve(fitted, exam)[1].max()
                                     for exam in exams]) * 1.18)
    left.set_xlabel("cohort ability percentile  (100 = top)")
    left.set_ylabel("test takers per cohort-percentile point")
    left.set_title(f"Fitted test-pool densities, {year}")
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
        f"{len(observations):,} matched threshold pairs, "
        f"disagreement {naive:.1f} → {error:.1f} percentile points",
        fontsize=11,
    )
    figure.tight_layout()
    figure.savefig(path, dpi=150)
    return path


def main():
    from pool import fit as pool_fit

    _, observations = pool_fit.observations()
    sizes = pool_fit.taker_counts()
    fitted, error = pool_fit.fit_pool(observations, sizes)
    written = draw(fitted, sizes, observations, error,
                   pool_fit.naive_error(observations), pool_fit.YEAR)
    print(f"wrote {written}")


if __name__ == "__main__":
    main()
