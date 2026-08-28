#!/usr/bin/env python3
"""Verify and compress ``pdftotext`` caches at a 50% default duty cycle.

Run ``python3 -m tools.compress_text_caches --dry-run`` to inspect the scope.
"""

import argparse
import gzip
import hashlib
import os
import time
from pathlib import Path

from lib.paths import source_path

CHUNK = 1 << 20

def digest(handle):
    running = hashlib.sha256()
    for block in iter(lambda: handle.read(CHUNK), b""):
        running.update(block)
    return running.hexdigest()

def compress(path, level=6):
    """Return a verified gzip copy of ``path``, leaving ``path`` untouched."""
    target = path.with_suffix(path.suffix + ".gz")
    temporary = target.with_suffix(target.suffix + ".part")
    before = hashlib.sha256()
    with path.open("rb") as source, gzip.open(
            temporary, "wb", compresslevel=level) as sink:
        for block in iter(lambda: source.read(CHUNK), b""):
            before.update(block)
            sink.write(block)
    with gzip.open(temporary, "rb") as check:
        if digest(check) != before.hexdigest():
            temporary.unlink(missing_ok=True)
            return None
    os.replace(temporary, target)
    return target

def pending(root):
    return sorted(root.rglob("*.txt"), key=lambda path: -path.stat().st_size)


def rest(spent, duty):
    return spent * (1 - duty) / duty if 0 < duty < 1 else 0.0

def run(root, duty=0.5, keep=False):
    files = pending(root)
    before = after = 0
    for index, path in enumerate(files, 1):
        started = time.monotonic()
        size = path.stat().st_size
        target = compress(path)
        if target is None:
            print(f"failed verification; retained {path}")
            continue
        before += size
        after += target.stat().st_size
        if not keep:
            path.unlink()
        print(f"{index:>3}/{len(files)}  {path.name}: "
              f"{size / 1e6:.2f} -> {target.stat().st_size / 1e6:.2f} MB")
        time.sleep(rest(time.monotonic() - started, duty))
    return before, after


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(source_path()))
    parser.add_argument("--duty", type=float, default=0.5)
    parser.add_argument("--keep", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not 0 < args.duty <= 1:
        parser.error("duty must be above zero and at most one")
    return args


def main(argv=None):
    args = arguments(argv)
    files = pending(args.root)
    total = sum(path.stat().st_size for path in files)
    print(f"{len(files)} text caches, {total / 1e6:.1f} MB")
    if args.dry_run:
        return
    try:
        os.nice(19)
    except OSError:
        pass
    before, after = run(args.root, args.duty, args.keep)
    if before:
        print(f"{before / 1e6:.1f} -> {after / 1e6:.1f} MB; "
              f"{(before - after) / 1e6:.1f} MB freed")


if __name__ == "__main__":
    main()
