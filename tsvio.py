"""Read and write the repository's tab-separated row dictionaries."""

import csv


def read_rows(path):
    with open(path, encoding="utf-8") as f:
        yield from csv.DictReader(f, delimiter="\t")


def write_rows(path, rows):
    """Write dictionaries using the first row's key order; return rows written."""
    columns = list(rows[0])
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, columns, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)
