"""Shared style, loaders, and output paths for the figures.

Every module here draws one figure and can be run on its own. The expensive
inputs — the ability curves and the scored thresholds behind them — are built
once per process and handed out from here.
"""

import functools

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402  (after the backend is fixed)

from lib import tsvio  # noqa: E402
from lib.paths import figure_path, ranking_path  # noqa: E402
from pool.plot import FONTS, STYLE  # noqa: E402

DPI = 150

# 一般大學 admit through 學測 and 指考; 科技大學 through 統測. Nothing else in the
# data separates the two systems, so the exams a seat was won on stand in.
TECH_EXAMS = ("tongce_a", "tongce_b", "tongce_c")
SYSTEM = {
    "general": ("#1f6feb", "一般大學 (學測 / 指考)"),
    "tech": ("#bc4c00", "科技大學 (統測)"),
}

# 頂/前/均/後/底標, as the percentile from the bottom that each marks.
BANDS = (("底標", 12), ("後標", 25), ("均標", 50), ("前標", 75), ("頂標", 88))


def start(**kwargs):
    """A figure with the CJK fonts in place, since every label needs them."""
    plt.rcParams["font.sans-serif"] = FONTS + plt.rcParams["font.sans-serif"]
    plt.rcParams["axes.unicode_minus"] = False
    return plt.subplots(**kwargs)


def finish(figure, name, title=None):
    figure.suptitle(title, fontsize=12) if title else None
    figure.tight_layout()
    target = figure_path(name)
    figure.savefig(target, dpi=DPI)
    plt.close(figure)
    print(f"  {name}")
    return target


# pool.plot styles the exams; 繁星 is scored off a class rank rather than an exam,
# so it needs its own entry to sit beside them.
EXTRA_STYLE = {"star": ("#8250df", "繁星 (class rank)")}


def style_of(exam):
    return EXTRA_STYLE.get(exam) or STYLE.get(exam) or ("#57606a", exam)


def label_of(exam):
    """The printed name of an exam, falling back to its key."""
    return style_of(exam)[1]


def colour_of(exam):
    return style_of(exam)[0]


def system_of(exams):
    """Which of the two university systems a set of exams belongs to."""
    return "tech" if any(exam in TECH_EXAMS for exam in exams) else "general"


def number(value):
    """A float from a TSV cell, or None where the column was left empty."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@functools.lru_cache(maxsize=None)
def table(name):
    """One of the generated ranking tables, as a list of dicts."""
    return list(tsvio.read_rows(ranking_path(name)))


@functools.lru_cache(maxsize=1)
def model():
    """The ability curves and every threshold read through them.

    Returns ``(splines, scored)`` where `scored` is the list of
    ``(row, exam, ability, seats)`` that `pool.ability` ranks departments on.
    """
    from pool import ability

    rows, splines = ability.curves()
    return splines, ability.read(rows, splines)


@functools.lru_cache(maxsize=1)
def by_department():
    """Scored thresholds regrouped as ``(school, dept) -> {exam: (level, seats)}``."""
    _, scored = model()
    out = {}
    for row, exam, level, seats in scored:
        seen = out.setdefault((row["school"], row["dept"]), {})
        held, weight = seen.get(exam, (0.0, 0.0))
        seen[exam] = (held + level * seats, weight + seats)
    return {key: {exam: (held / weight, weight)
                  for exam, (held, weight) in seen.items() if weight}
            for key, seen in out.items()}
