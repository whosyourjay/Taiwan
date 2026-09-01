#!/usr/bin/env python3
"""Generate English labels for every ranked school, department and group."""

from lib.english import CACHE, english_names, load_cache
from pool import ability


def main():
    rows = ability.admission_rows()
    names = {
        row[field]
        for row in rows
        for field in ("school", "dept", "application_group")
        if row.get(field)
    }
    before = len(load_cache())
    translated = english_names(names, translate_missing=True)
    print(f"{len(names)} labels, {len(translated) - before} newly translated")
    print(f"Cache holds {len(translated)} labels at {CACHE}")


if __name__ == "__main__":
    main()
