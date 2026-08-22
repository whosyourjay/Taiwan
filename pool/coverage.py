"""Compare the seats we hold on each path against the published path totals.

The tiling normalises against the assessment pool, so every seat we are missing
lands in the chunk at the bottom and lifts every department above it. This says
how big that error is, path by path.
"""


if __package__ in (None, ""):
    import _bootstrap  # noqa: F401

from pool import fit as pool_fit
from pool import tiling


def main():
    year = pool_fit.YEAR
    rows, _ = pool_fit.observations()
    order, schools = tiling.ranked()
    groups = tiling.grouped()
    filled = tiling.admitted(year)
    placed = list(tiling.placed_rows(rows, order, schools, groups))
    scales = tiling.path_scales(placed, filled)
    cohort = tiling.assessment_size(year)
    print(f"\n{year} seats held against published totals")
    seated = 0.0
    for path, scale in sorted(scales.items()):
        theirs = filled.get(tiling.TOTAL_NAMES.get(path, path), 0.0)
        mine = sum(float(row["seats"]) for row, _, _ in placed
                   if row["path"] == path)
        seated += mine * scale
        share = f"{100 * mine / theirs:5.1f}%" if theirs else "     -"
        print(f"  {path:<12}{mine:>9,.0f}{theirs:>9,.0f}{share:>9}")
    print(f"\n{seated:,.0f} seats placed among {cohort:,.0f} test takers, so the bottom"
          f" chunk is {100 * (1 - seated / cohort):.1f}% of the assessment pool")


if __name__ == "__main__":
    main()
