"""Which annual path cells supply direct bars to the longitudinal model.

This distinguishes direct threshold evidence from the annual panel's explicit
seat and ability imputations, and shows how much published intake the bars cover.
"""

import collections
import sys

import numpy as np

from lib import tsvio
from lib.paths import data_path
from viz import common

NAME = "collected.png"
# Path -> the file its bars come from, and the column holding the seat count.
SOURCES = (
    ("uac", "uac-cutoffs.tsv", "seats"),
    ("tech", "tech-cutoffs.tsv", "seats"),
    ("star", "star-cutoffs.tsv", "admitted"),
    ("apply", "apply-cutoffs.tsv", "seats"),
    ("tech_apply", "tech-apply-cutoffs.tsv", "seats"),
)
LABELS = {"uac": "分發入學", "tech": "四技登記分發", "star": "繁星推薦",
          "apply": "個人申請", "tech_apply": "四技甄選"}


def counted():
    """``(path, year) -> (bars, seats)`` over every cutoff table."""
    out = collections.defaultdict(lambda: [0, 0.0])
    for path, source, column in SOURCES:
        for row in tsvio.read_rows(data_path(source)):
            cell = out[(path, row["year"])]
            cell[0] += 1
            cell[1] += common.number(row.get(column)) or 0.0
    return {key: tuple(value) for key, value in out.items()}


def published():
    """``(path, year) -> admitted``, with 甄選 under the name its bars use."""
    names = {"tech_select": "tech_apply"}
    return {(names.get(row["path"], row["path"]), row["year"]):
            float(row["admitted"])
            for row in tsvio.read_rows(data_path("admission-totals.tsv"))}


def grid(bars, totals):
    """Coverage as a paths x years matrix, NaN where nothing was collected."""
    years = sorted({year for _, year in bars} | {year for _, year in totals})
    paths = [path for path, *_ in SOURCES]
    shares = np.full((len(paths), len(years)), np.nan)
    for r, path in enumerate(paths):
        for c, year in enumerate(years):
            held = bars.get((path, year))
            total = totals.get((path, year))
            if held and total:
                shares[r][c] = 100 * held[1] / total
            elif held:
                shares[r][c] = 0.0
    return paths, years, shares


def annotate(panel, paths, years, shares, bars):
    for r, path in enumerate(paths):
        for c, year in enumerate(years):
            held = bars.get((path, year))
            if not held:
                panel.annotate("—", xy=(c, r), ha="center", va="center",
                               fontsize=11, color="#8c959f")
                continue
            share = shares[r][c]
            tone = "#ffffff" if share > 55 else "#24292f"
            text = f"{held[0]:,} bars\n{held[1]:,.0f} seats"
            if share:
                text += f"\n{share:.0f}% of intake"
            panel.annotate(text, xy=(c, r), ha="center", va="center", fontsize=8,
                           color=tone)


def draw(bars, totals, name=NAME):
    paths, years, shares = grid(bars, totals)
    figure, panel = common.start(figsize=(12.5, 5.2))
    panel.imshow(np.nan_to_num(shares), cmap="Blues", vmin=0, vmax=110,
                 aspect="auto")
    annotate(panel, paths, years, shares, bars)
    panel.set_xticks(range(len(years)))
    panel.set_xticklabels([f"{y} 學年度\n({int(y) + 1911})" for y in years])
    panel.set_yticks(range(len(paths)))
    panel.set_yticklabels([f"{LABELS[p]}\n{p}" for p in paths])
    panel.set_xticks(np.arange(-0.5, len(years), 1), minor=True)
    panel.set_yticks(np.arange(-0.5, len(paths), 1), minor=True)
    panel.grid(which="minor", color="#ffffff", linewidth=2)
    panel.tick_params(which="minor", length=0)
    return common.finish(
        figure, name,
        "What the repository holds — shading is the share of that path's"
        " published intake")


def main():
    draw(counted(), published())
    return 0


if __name__ == "__main__":
    sys.exit(main())
