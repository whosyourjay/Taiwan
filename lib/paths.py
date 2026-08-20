"""Stable locations for repository resources and derived tables."""

import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def path(*parts):
    """Absolute path to a repository resource, e.g. ``path("data", "a.tsv")``."""
    return os.path.join(ROOT, *parts)


def source_path(*parts):
    """Absolute path to a downloaded source, e.g. ``source_path("star", "a.pdf")``."""
    return path("sources", *parts)


def data_path(*parts):
    """Absolute path to parsed or published input data."""
    return path("data", *parts)


def ranking_path(*parts):
    """Absolute path to generated ranking tables."""
    return path("rankings", *parts)


def figure_path(*parts):
    """Absolute path to a generated figure, creating the directory as needed."""
    target = path("figures", *parts)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    return target
