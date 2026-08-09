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


def draw(points, fitted, total, out=OUT):
    plt.rcParams["font.sans-serif"] = FONTS + plt.rcParams["font.sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    figure, axes = plt.subplots(1, 2, figsize=(13, 5.4))
    exams = sorted(points)

    scatter, lines = axes

    for exam in exams:
        colour, label = STYLE.get(exam, ("#57606a", exam))
        got = points[exam]
        scatter.scatter([100 * (1 - t) for t, _, _ in got],
                        [100 * a for _, a, _ in got],
                        s=[max(2.0, s / 6) for _, _, s in got], color=colour,
                        alpha=0.22, linewidths=0, label=label)
    scatter.set_title("Every department-path, sized by seats")
    lines.set_title("The curve those departments imply")

    for exam in exams:
        colour, label = STYLE.get(exam, ("#57606a", exam))
        tops, levels = fitted[exam]
        lines.plot(100 * (1 - tops), 100 * levels, color=colour, linewidth=2.4,
                   label=f"{label}  ({len(tops):,} distinct bars)")

    for panel in (scatter, lines):
        panel.plot([0, 100], [0, 100], color="#57606a", linewidth=1.0,
                   linestyle="--", label="if percentiles transferred directly")
        panel.set_xlim(0, 100)
        panel.set_ylim(0, 100)
        panel.set_xlabel("bottom % of that exam's takers")
        panel.set_ylabel("percentile among university admits")
        panel.legend(loc="upper left", frameon=False, fontsize=9)
        panel.grid(alpha=0.18)

    figure.suptitle(
        f"What a rank inside one exam is worth — read off the department "
        f"ranking, {total:,.0f} seats tiled",
        fontsize=11,
    )
    figure.tight_layout()
    figure.savefig(out, dpi=150)
    return out
