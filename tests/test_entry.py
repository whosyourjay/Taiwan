"""Tests for CAP statistics and high-school entrance-cutoff parsers."""

import random
import unittest

from fetch import entry as fetcher
from lib.paths import path
from parse import cap, entry


def cutoff_page(rows):
    return """<html><table><caption>107基北區高中錄取分數排序</caption>
    <tr><th>學校</th><th>錄取分數</th></tr>{}</table></html>""".format(rows)


def cutoff_row(school, score):
    return f"<tr><td>{school}</td><td>{score}</td></tr>"


def cap_page(rows):
    return "<table>{}</table>".format(rows)


def cap_row(category, students, pct):
    return f"<tr><td>{category}</td><td>{students}</td><td>{pct}%</td></tr>"


class TestFetch(unittest.TestCase):
    def test_107_sources(self):
        self.assertIn("moe.gov.tw", fetcher.SOURCES["cap-107-statistics"]["url"])
        self.assertIn("tkbgo.com.tw", fetcher.SOURCES["jibei-107-cutoffs"]["url"])


class TestCutoffs(unittest.TestCase):
    def test_reads_the_named_table(self):
        html = cutoff_page(cutoff_row("北一女中", "33.8"))
        self.assertEqual(entry.parse_html(html)[0]["school"], "北一女中")

    def test_random_valid_cutoffs(self):
        rng = random.Random(20260809)
        for _ in range(100):
            score = rng.uniform(0, entry.CAP_MAX)
            html = cutoff_page(cutoff_row("某高中", f"{score:.1f}"))
            self.assertAlmostEqual(entry.parse_html(html)[0]["cap_score"], score, places=1)

    def test_rejects_scores_outside_the_cap_scale(self):
        html = cutoff_page(cutoff_row("某高中", "36.1"))
        with self.assertRaisesRegex(ValueError, "out of range"):
            entry.parse_html(html)


class TestDistribution(unittest.TestCase):
    def test_reads_achievement_categories(self):
        html = cap_page(
            cap_row("5A0B0C", "17619", "7.77")
            + cap_row("4A1B0C", "10556", "4.66")
        )
        self.assertEqual(cap.parse_html(html)[1]["students"], 10556)


class TestOfficialSources(unittest.TestCase):
    def test_cutoff_spots_and_count(self):
        source = path("entry", fetcher.SOURCES["jibei-107-cutoffs"]["filename"])
        with open(source, encoding="utf-8") as f:
            rows = entry.parse_html(f.read())
        by_school = {row["school"]: row["cap_score"] for row in rows}
        self.assertEqual(len(rows), 52)
        self.assertEqual(by_school["建國中學"], 33.8)
        self.assertEqual(by_school["北一女中"], 33.8)
        self.assertEqual(by_school["基隆高中"], 8.6)

    def test_cap_categories_sum_to_official_valid_candidates(self):
        source = path("entry", fetcher.SOURCES["cap-107-statistics"]["filename"])
        with open(source, encoding="utf-8") as f:
            rows = cap.parse_html(f.read())
        self.assertEqual(sum(row["students"] for row in rows), 226639)


if __name__ == "__main__":
    unittest.main()
