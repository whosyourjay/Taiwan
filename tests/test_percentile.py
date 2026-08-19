"""Tests for ranking one 學測 total against the cohort and the admitted pool."""

import csv
import collections
import os
import random
import unittest

import ceec_score
from lib.paths import data_path
from parse import ceec as parse_ceec
from pool import percentile

TOTALS = parse_ceec.TOTAL_SUBJECT
LABEL = "國英數社自"
# Few draws per run, unseeded, so successive runs cover different scores rather
# than one run covering them all. FUZZ=2000 pytest ... to chase a failure.
FUZZ = int(os.environ.get("FUZZ", 30))
# Building the real curves costs a second and says nothing about monotonicity,
# which is a property of the lookup either way.
STRAIGHT = {percentile.EXAM: (lambda below: below)}


def gsat_rows():
    with open(data_path("ceec-scores.tsv"), encoding="utf-8") as f:
        return [row for row in csv.DictReader(f, delimiter="\t")
                if row["exam"] == "gsat"]


def five_subject_years():
    return sorted({row["year"] for row in gsat_rows() if row["subject"] == TOTALS})


class TestSubjectNaming(unittest.TestCase):
    def test_the_parsed_total_is_spelled_the_way_a_bar_is_read(self):
        # The parser writes one spelling and top_fraction looks up another; if
        # they drift apart every five-subject lookup silently returns None.
        self.assertEqual("、".join(ceec_score.split_subjects(LABEL)), TOTALS)


class TestParsedTotals(unittest.TestCase):
    def test_every_five_subject_year_covers_the_whole_scale(self):
        rows = [row for row in gsat_rows() if row["subject"] == TOTALS]
        self.assertTrue(rows, "no five-subject totals were parsed")
        by_year = collections.defaultdict(list)
        for row in rows:
            by_year[row["year"]].append(float(row["score"]))
        for year, scores in by_year.items():
            self.assertEqual(min(scores), 0.0, year)
            self.assertEqual(max(scores), float(parse_ceec.TOTAL_MAX), year)
            self.assertEqual(len(scores), len(set(scores)), year)

    def test_totals_and_combinations_never_describe_one_year(self):
        # Both would be five-subject evidence for the same cohort, and the
        # lookup has no way to prefer one, so the year ranges have to be split.
        combos = {row["year"] for row in gsat_rows() if "、" in row["subject"]
                  and row["subject"] != TOTALS}
        self.assertFalse(combos & set(five_subject_years()))


class TestRank(unittest.TestCase):
    def setUp(self):
        cohort = ceec_score.CohortPercentiles.load(data_path("ceec-scores.tsv"))
        self.loaded = (cohort, STRAIGHT)

    def test_rank_is_monotone_and_bounded(self):
        years = five_subject_years()
        self.assertTrue(years)
        for _ in range(FUZZ):
            year = random.choice(years)
            low = random.randint(0, parse_ceec.TOTAL_MAX)
            high = random.randint(low, parse_ceec.TOTAL_MAX)
            below_low, level_low = percentile.rank(year, LABEL, low, self.loaded)
            below_high, level_high = percentile.rank(year, LABEL, high, self.loaded)
            for got in (below_low, below_high, level_low, level_high):
                self.assertIsNotNone(got)
                self.assertGreaterEqual(got, 0.0)
                self.assertLessEqual(got, 1.0)
            self.assertLessEqual(below_low, below_high + 1e-12)
            self.assertLessEqual(level_low, level_high + 1e-12)

    def test_an_unpublished_subject_set_is_reported_rather_than_guessed(self):
        # 108 onwards publishes combinations instead, so the five-subject total
        # is genuinely absent rather than zero.
        self.assertEqual(percentile.rank("114", LABEL, 60, self.loaded), (None, None))
        self.assertEqual(percentile.rank("103", "英聽", 10, self.loaded), (None, None))


if __name__ == "__main__":
    unittest.main()
