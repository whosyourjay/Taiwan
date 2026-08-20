"""Build every figure. ``python3 -m viz`` for all, or name the ones you want."""

import argparse
import sys

from viz import agreement, bridge, collected, relationships, spectrum

FIGURES = {
    "spectrum": spectrum,
    "agreement": agreement,
    "bridge": bridge,
    "collected": collected,
    "relationships": relationships,
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("figures", nargs="*", metavar="FIGURE",
                        help=f"which to build, from {', '.join(FIGURES)}"
                             " (default: all)")
    args = parser.parse_args(argv)

    unknown = [name for name in args.figures if name not in FIGURES]
    if unknown:
        parser.error(f"no such figure: {', '.join(unknown)}")

    return sum(FIGURES[name].main() or 0 for name in args.figures or FIGURES)


if __name__ == "__main__":
    sys.exit(main())
