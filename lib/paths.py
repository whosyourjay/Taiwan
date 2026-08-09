"""Data files live in the repository root, whatever package reads them."""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def path(*parts):
    """Absolute path to a repository file, e.g. path("star", "*.pdf")."""
    return os.path.join(ROOT, *parts)
