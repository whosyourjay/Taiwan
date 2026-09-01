"""Compare named threshold seats with published annual path totals."""


if __package__ in (None, ""):
    import _bootstrap  # noqa: F401

from pool import tiling


def main():
    from pool import ability

    rows = ability.admission_rows()
    for year in ability.YEARS:
        current = [row for row in rows if row["year"] == year]
        filled = tiling.admitted(year)
        if not filled:
            continue
        print(f"\n{year} named seats held against published totals")
        for path in sorted({row["path"] for row in current}):
            mine = sum(float(row["seats"]) for row in current if row["path"] == path)
            theirs = filled.get(tiling.TOTAL_NAMES.get(path, path), 0.0)
            share = f"{100 * mine / theirs:5.1f}%" if theirs else "     -"
            print(f"  {path:<12}{mine:>9,.0f}{theirs:>9,.0f}{share:>9}")


if __name__ == "__main__":
    main()
