"""Draw each exam's bar-to-ability curve over the departments it came from.

Every dot is one department-path: where its cutoff sits among its exam's takers,
against where its admits sit in the admitted pool. Dot area is seats. The line
through them is the curve those dots imply, which can only rise.
"""

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (after the backend is fixed)

from lib.paths import path  # noqa: E402
from pool.plot import FONTS, STYLE  # noqa: E402

OUT = path("tiling-curves.png")


def draw(points, fitted, smoothed, shares, total, out=OUT):
    plt.rcParams["font.sans-serif"] = FONTS + plt.rcParams["font.sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    figure, (scatter, lines, mix) = plt.subplots(1, 3, figsize=(17.5, 5.4))
    exams = sorted(points)
    grid = np.linspace(0.0, 1.0, 400)

    for exam in exams:
        colour, label = STYLE.get(exam, ("#57606a", exam))
        got = points[exam]
        scatter.scatter([100 * (1 - t) for t, _, _ in got],
                        [100 * a for _, a, _ in got],
                        s=[max(2.0, s / 6) for _, _, s in got], color=colour,
                        alpha=0.22, linewidths=0, label=label)
        tops, levels = fitted[exam]
        lines.step(100 * (1 - tops), 100 * levels, where="post", color=colour,
                   linewidth=1.0, alpha=0.35)
        lines.plot(100 * grid, 100 * smoothed[exam](grid), color=colour,
                   linewidth=2.4, label=f"{label}  ({len(tops):,} distinct bars)")
    scatter.set_title("Every department-path, sized by seats")
    lines.set_title("Smoothed, over the bars it came from")

    for panel in (scatter, lines):
        panel.plot([0, 100], [0, 100], color="#57606a", linewidth=1.0,
                   linestyle="--", label="if percentiles transferred directly")
        panel.set_xlim(0, 100)
        panel.set_ylim(0, 100)
        panel.set_xlabel("bottom % of that exam's takers")
        panel.set_ylabel("percentile among university admits")
        panel.legend(loc="upper left", frameon=False, fontsize=9)
        panel.grid(alpha=0.18)

    axis = np.linspace(0.0, 100.0, len(next(iter(shares.values()))))
    floor = np.zeros_like(axis)
    for exam in exams:
        colour, label = STYLE.get(exam, ("#57606a", exam))
        top = floor + shares[exam] * total / 100.0
        mix.fill_between(axis, floor, top, color=colour, alpha=0.55,
                         linewidth=0, label=f"{label}  ({shares[exam].mean() * total:,.0f} seats)")
        floor = top
    mix.set_xlim(0, 100)
    mix.set_ylim(0, total / 100.0)
    mix.set_xlabel("percentile among university admits")
    mix.set_ylabel("seats per admit-percentile point")
    mix.set_title("Which exam fills the pool, at each ability")
    mix.legend(loc="lower left", frameon=False, fontsize=9)
    mix.grid(alpha=0.18)

    figure.suptitle(
        f"What a rank inside one exam is worth — read off the department "
        f"ranking, {total:,.0f} seats tiled",
        fontsize=11,
    )
    figure.tight_layout()
    figure.savefig(out, dpi=150)
    return out
