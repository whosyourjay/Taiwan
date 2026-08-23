"""Tests for the 學測 cohort percentiles and the paths that depend on them."""

import random
import unittest

from rank import ceec_score
from rank import uac
from lib import tsvio
from lib.paths import data_path

SCORES = data_path("ceec-scores.tsv")
STAR = data_path("star-cutoffs.tsv")

# 頂/前/均/後/底標 is the 級分 of the candidate at this percentile from the bottom.
BANDS = [("頂標", 88), ("前標", 75), ("均標", 50), ("後標", 25), ("底標", 12)]


def rows(year, subject, counts):
    return [{"year": year, "exam": "gsat", "subject": subject,
             "score": score, "seats": seats} for score, seats in counts]


class TestSplitSubjects(unittest.TestCase):
    def test_full_names_and_abbreviations(self):
        self.assertEqual(ceec_score.split_subjects("國文英文社會"),
                         ["國文", "英文", "社會"])
        self.assertEqual(ceec_score.split_subjects("國英數自"),
                         ["國文", "英文", "數學", "自然"])

    def test_prefers_the_longer_subject_name(self):
        # 數學A must not read as 數學 followed by a stray A, nor 數A as 數 + A.
        self.assertEqual(ceec_score.split_subjects("數學A"), ["數學A"])
        self.assertEqual(ceec_score.split_subjects("數A"), ["數學A"])
        self.assertEqual(ceec_score.split_subjects("國英數A自"),
                         ["國文", "英文", "數學A", "自然"])

    def test_unknown_label_is_rejected_whole(self):
        # A partial parse would score the row against the wrong subject set.
        self.assertIsNone(ceec_score.split_subjects("國文術科"))
        self.assertIsNone(ceec_score.split_subjects(""))

    def test_fuzz_round_trips_any_combination(self):
        names = ["國文", "英文", "數學A", "數學B", "社會", "自然"]
        short = {v: k for k, v in ceec_score.GSAT_FULL.items()}
        rng = random.Random(20260809)
        for _ in range(500):
            picked = rng.sample(names, rng.randint(1, len(names)))
            for spelling in (picked, [short.get(n, n) for n in picked]):
                self.assertEqual(
                    ceec_score.split_subjects("".join(spelling)), picked
                )


class TestCohortPercentiles(unittest.TestCase):
    def setUp(self):
        self.cohort = ceec_score.CohortPercentiles(
            rows("114", "國文", [(15, 10), (14, 30), (13, 60)])
        )

    def test_share_above_the_bar_splits_its_own_bucket(self):
        self.assertAlmostEqual(self.cohort.top_fraction("114", "國文", 15), 0.05)
        self.assertAlmostEqual(self.cohort.top_fraction("114", "國文", 14), 0.25)
        self.assertAlmostEqual(self.cohort.top_fraction("114", "國文", 13), 0.70)

    def test_score_buckets_retain_the_full_tied_interval(self):
        got = self.cohort.score_buckets("114", "國文")
        self.assertEqual(got[-1], (0.9, 1.0, 15.0, 10.0))

    def test_unknown_subject_or_year_is_none(self):
        self.assertIsNone(self.cohort.top_fraction("114", "英聽", 5))
        self.assertIsNone(self.cohort.top_fraction("113", "國文", 15))

    def test_monotone_in_the_bar(self):
        got = [self.cohort.top_fraction("114", "國文", s) for s in (13, 14, 15)]
        self.assertEqual(got, sorted(got, reverse=True))

    def test_strictest_gate_uses_the_rarest_binding_subject(self):
        got = self.cohort.strictest_gate_percentile(
            "114", "國文頂標15 國文前標14 英聽頂標5"
        )
        self.assertAlmostEqual(got, 0.95)

    def test_binding_gates_retain_the_subject(self):
        got = self.cohort.binding_gates("114", "國文頂標15 英聽頂標5")
        self.assertEqual(got, [("國文", 0.05)])

    def test_no_recognised_gate_has_no_gate_coordinate(self):
        self.assertEqual(self.cohort.strictest_gate_percentile("114", "英聽頂標5"), 0.0)


class TestAgainstPublishedBands(unittest.TestCase):
    """The 級分 tables must reproduce the 檢定標準 printed in the 繁星 PDFs.

    The two come from different files parsed by different code, so agreement
    checks that the distributions were read onto the right scale.
    """

    def test_band_boundaries_match_the_star_gates(self):
        cohort = ceec_score.CohortPercentiles.load(SCORES)
        printed = {}
        for row in tsvio.read_rows(STAR):
            for token in row["gates"].split():
                for name, _ in BANDS:
                    if name in token:
                        subject, level = token.split(name)
                        printed[(row["year"], subject, name)] = int(level)
        self.assertTrue(printed, "no 檢定標準 parsed out of star-cutoffs.tsv")

        checked = 0
        for (year, subject, name), level in sorted(printed.items()):
            counts = cohort.counts.get((year, subject))
            if not counts:
                continue
            percentile = dict(BANDS)[name]
            total = sum(counts.values())
            below = 0.0
            for score in sorted(counts):
                below += counts[score]
                if 100.0 * below / total >= percentile:
                    break
            self.assertEqual(int(score), level, f"{year} {subject} {name}")
            checked += 1
        self.assertGreater(checked, 20, "too few bands covered to be meaningful")


class TestAbsolutePathsIgnoreTheSample(unittest.TestCase):
    """A path scored against a national cohort must not be re-ranked locally.

    Curving replaces the value with a position among the rows collected next to
    it, so dropping unrelated schools would move a department that did not
    change. Everything here is about that invariant.
    """

    def make_rows(self, extra=()):
        base = [
            {"year": "111", "path": "apply", "basis": 90.0, "seats": 10},
            {"year": "111", "path": "apply", "basis": 60.0, "seats": 10},
        ]
        return base + [dict(r) for r in extra]

    def curve_all(self, rows):
        uac.curve([r for r in rows if r["path"] not in uac.ABSOLUTE],
                       "basis", "pct", lambda r: (r["year"], r["path"]))
        for row in rows:
            if row["path"] in uac.ABSOLUTE:
                row["pct"] = row["basis"]

    def test_absolute_basis_passes_through_untouched(self):
        rows = self.make_rows()
        self.curve_all(rows)
        self.assertEqual([r["pct"] for r in rows], [90.0, 60.0])

    def test_adding_a_school_does_not_move_the_others(self):
        alone = self.make_rows()
        self.curve_all(alone)
        together = self.make_rows(
            [{"year": "111", "path": "apply", "basis": 99.0, "seats": 400}]
        )
        self.curve_all(together)
        self.assertEqual([r["pct"] for r in together[:2]],
                         [r["pct"] for r in alone])

    def test_a_curved_path_does_move(self):
        # The contrast the invariant is protecting against.
        rows = [{"year": "111", "path": "tech", "basis": b, "seats": 10}
                for b in (90.0, 60.0)]
        self.curve_all(rows)
        before = [r["pct"] for r in rows]
        rows.append({"year": "111", "path": "tech", "basis": 99.0, "seats": 400})
        self.curve_all(rows)
        self.assertNotEqual([r["pct"] for r in rows[:2]], before)


class TestInterpolateEnds(unittest.TestCase):
    def test_holds_flat_beyond_the_data(self):
        xs, ys = [0.0, 10.0], [0.0, 100.0]
        self.assertAlmostEqual(ceec_score.interpolate(xs, ys, 20.0), 100.0)
        self.assertAlmostEqual(ceec_score.interpolate(xs, ys, -5.0), 0.0)
        self.assertAlmostEqual(ceec_score.interpolate(xs, ys, 2.5), 25.0)

    def test_tied_x_takes_the_last_of_the_tie(self):
        # bisect_right lands past the whole run, so no zero-width segment arises.
        self.assertAlmostEqual(
            ceec_score.interpolate([0.0, 5.0, 5.0, 9.0], [0.0, 1.0, 2.0, 3.0], 5.0),
            2.0,
        )


if __name__ == "__main__":
    unittest.main()
