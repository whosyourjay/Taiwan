"""Tests for the cohort-ability model."""

import os
import subprocess
import sys
import unittest
from unittest import mock

import numpy as np
import pytest

from parse import tcte
from pool import complement
from pool import model as pool
from pool import plot as pool_plot
from pool import fit as pool_fit


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestAbility(unittest.TestCase):
    def test_uniform_takers_are_their_own_percentile(self):
        # An exam sat by a flat slice of the cohort needs no correction.
        flat = pool.AbilityPool({"e": [1 / 3, 1 / 3, 1 / 3]}, 3)
        for top in (0.0, 0.1, 0.25, 0.5, 0.75, 1.0):
            self.assertAlmostEqual(flat.ability("e", top), 1 - top, places=9)

    def test_top_heavy_exam_pushes_bars_down_the_cohort(self):
        # All takers in the top third: their top 50% is the cohort's top sixth.
        top_third = pool.AbilityPool({"e": [0.0, 0.0, 1.0]}, 3)
        self.assertAlmostEqual(top_third.ability("e", 0.5), 1 - 1 / 6, places=9)
        self.assertAlmostEqual(top_third.ability("e", 1.0), 2 / 3, places=9)

    def test_monotone_and_bounded(self):
        skewed = pool.AbilityPool({"e": [0.5, 0.2, 0.3]}, 3)
        got = [skewed.ability("e", t) for t in np.linspace(0, 1, 21)]
        self.assertEqual(got, sorted(got, reverse=True))
        self.assertTrue(all(0.0 <= g <= 1.0 for g in got))

    def test_clamps_out_of_range_input(self):
        flat = pool.AbilityPool({"e": [0.5, 0.5]}, 2)
        self.assertAlmostEqual(flat.ability("e", -1.0), 1.0)
        self.assertAlmostEqual(flat.ability("e", 2.0), 0.0)

    def test_random_pdfs_integrate_to_observed_takers(self):
        rng = np.random.default_rng(20260809)
        for _ in range(100):
            shares = rng.dirichlet(np.ones(3))
            size = float(rng.integers(1, 200_000))
            fitted = pool.AbilityPool({"e": shares}, 3, {"e": size})
            self.assertAlmostEqual(float(fitted.bin_counts("e").sum()), size)
            area = float(fitted.percentile_density("e").sum()) * 100 / 3
            self.assertAlmostEqual(area, size)

    def test_exam_size_scales_only_its_independent_pdf(self):
        shares = {"a": [0.2, 0.3, 0.5], "b": [0.4, 0.4, 0.2]}
        smaller = pool.AbilityPool(shares, 3, {"a": 10, "b": 40})
        larger = pool.AbilityPool(shares, 3, {"a": 100, "b": 40})
        self.assertAlmostEqual(smaller.ability("a", 0.25),
                               larger.ability("a", 0.25))
        np.testing.assert_allclose(smaller.density("b"), larger.density("b"))
        np.testing.assert_allclose(larger.density("a"), 10 * smaller.density("a"))

    def test_uniform_linear_pool_is_its_own_percentile(self):
        linear = pool.LinearAbilityPool({"e": [1.0, 1.0, 1.0]}, {"e": 10})
        for top in (0.0, 0.1, 0.25, 0.5, 0.75, 1.0):
            self.assertAlmostEqual(linear.ability("e", top), 1 - top, places=9)

    def test_linear_pool_integrates_to_every_exam_count(self):
        linear = pool.LinearAbilityPool(
            {"a": [1.5, 1.0, 0.5], "b": [0.5, 1.0, 1.5]},
            {"a": 30, "b": 70},
        )
        for exam in linear.exams:
            self.assertAlmostEqual(linear.bin_counts(exam).sum(), linear.sizes[exam])


class TestMatched(unittest.TestCase):
    def rows(self):
        return [
            {"year": "110", "school": "A", "dept": "X", "exam": "p", "top": 0.10,
             "seats": 30},
            {"year": "110", "school": "A", "dept": "X", "exam": "q", "top": 0.20,
             "seats": 10},
            {"year": "110", "school": "A", "dept": "Y", "exam": "p", "top": 0.40,
             "seats": 5},
        ]

    def test_pairs_only_departments_in_two_exams(self):
        got = pool.matched(self.rows(), lambda r: r["exam"], lambda r: r["top"])
        self.assertEqual(len(got), 1)
        exam_a, top_a, exam_b, top_b, weight = got[0]
        self.assertEqual((exam_a, exam_b), ("p", "q"))
        self.assertAlmostEqual(top_a, 0.10)
        self.assertAlmostEqual(top_b, 0.20)
        self.assertEqual(weight, 10, "weight is the smaller intake")

    def test_skips_rows_with_no_exam_or_no_bar(self):
        got = pool.matched(self.rows(), lambda r: None, lambda r: r["top"])
        self.assertEqual(got, [])
        got = pool.matched(self.rows(), lambda r: r["exam"], lambda r: None)
        self.assertEqual(got, [])

    def test_several_rows_average_by_seats(self):
        rows = self.rows() + [
            {"year": "110", "school": "A", "dept": "X", "exam": "p", "top": 0.30,
             "seats": 10}
        ]
        got = pool.matched(rows, lambda r: r["exam"], lambda r: r["top"])
        # (0.10*30 + 0.30*10) / 40
        self.assertAlmostEqual(got[0][1], 0.15)

    def test_matched_groups_keep_pairs_with_their_department(self):
        got = pool.matched_groups(
            self.rows(), lambda row: row["exam"], lambda row: row["top"]
        )
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0][0], ("110", "A", "X"))
        self.assertEqual(got[0][1], pool.matched(
            self.rows(), lambda row: row["exam"], lambda row: row["top"]
        ))


class TestTechApplyRows(unittest.TestCase):
    def test_loads_binding_110_gsat_screen_only(self):
        rows = [
            {
                "year": "110", "school": "A", "dept": "工程系甲組",
                "subjects": "國文x1.00", "cutoff": "10", "seats": "20",
            },
            {
                "year": "110", "school": "A", "dept": "管理系",
                "subjects": "國文x1.00", "cutoff": "1", "seats": "10",
            },
            {
                "year": "109", "school": "A", "dept": "資訊系",
                "subjects": "國文x1.00", "cutoff": "10", "seats": "5",
            },
        ]
        distributions = mock.Mock()
        distributions.gsat_percentile.side_effect = [0.75, 0.01, 0.75]
        with mock.patch.object(pool_fit.tsvio, "read_rows", return_value=rows):
            got = pool_fit.load_tech_apply(distributions)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["path"], "tech_apply")
        self.assertEqual(got[0]["dept"], "工程系")
        self.assertEqual(got[0]["seats"], 20)
        self.assertAlmostEqual(pool_fit.top_of(got[0]), 0.25)


class TestFit(unittest.TestCase):
    def observations_from(self, truth, bars):
        """Bars that agree exactly under `truth`, so a good fit recovers it."""
        out = []
        for top_a in bars:
            ability = truth.ability("a", top_a)
            lo, hi = 0.0, 1.0
            for _ in range(60):
                mid = (lo + hi) / 2
                if truth.ability("b", mid) > ability:
                    lo = mid
                else:
                    hi = mid
            out.append(("a", top_a, "b", (lo + hi) / 2, 1.0))
        return out

    def test_recovers_a_known_warp(self):
        truth = pool.AbilityPool({"a": [1 / 3, 1 / 3, 1 / 3],
                                  "b": [0.15, 0.30, 0.55]}, 3)
        bars = [0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 0.70]
        observations = self.observations_from(truth, bars)
        self.assertLess(pool.residual(truth, observations), 0.01)

        sizes = {"a": 90, "b": 40}
        fitted, error = pool.fit(observations, ["a", "b"], sizes, bins=3,
                                 smooth=0.0, restarts=4)
        self.assertLess(error, 0.6, "fit should reproduce agreeing bars")
        for top in (0.05, 0.25, 0.5):
            self.assertAlmostEqual(fitted.ability("a", top),
                                   fitted.ability("b", self.matching(fitted, top)),
                                   places=2)

    def matching(self, fitted, top_a):
        ability = fitted.ability("a", top_a)
        lo, hi = 0.0, 1.0
        for _ in range(60):
            mid = (lo + hi) / 2
            if fitted.ability("b", mid) > ability:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2

    def test_shares_stay_a_distribution(self):
        observations = self.observations_from(
            pool.AbilityPool({"a": [0.4, 0.3, 0.3], "b": [0.2, 0.3, 0.5]}, 3),
            [0.05, 0.2, 0.5],
        )
        fitted, _ = pool.fit(observations, ["a", "b"], {"a": 90, "b": 40},
                             bins=3, restarts=2)
        for shares in fitted.shares.values():
            self.assertAlmostEqual(float(shares.sum()), 1.0, places=9)
            self.assertTrue((shares > 0).all())

    def test_no_observations_is_an_error(self):
        with self.assertRaises(ValueError):
            pool.fit([], ["a", "b"], {"a": 90, "b": 40})

    def test_requires_observed_count_for_every_exam(self):
        observations = [("a", 0.1, "b", 0.2, 1.0)]
        with self.assertRaisesRegex(ValueError, "missing observed taker counts"):
            pool.fit(observations, ["a", "b"], {"a": 90})

    def test_two_line_fit_caps_exam_density_at_the_original_cohort(self):
        observations = [
            ("gsat", 0.1, "tongce", 0.2, 1.0),
            ("gsat", 0.2, "zhikao", 0.2, 1.0),
            ("tongce", 0.3, "zhikao", 0.3, 1.0),
        ]
        sizes = {"gsat": 100, "tongce": 80, "zhikao": 20}
        fitted, _ = pool.fit_two_line(
            observations, sorted(sizes), sizes, require_unimodal=False
        )
        cohort = pool.cohort_size(sizes)
        self.assertEqual(fitted.values["zhikao"][-1], 0.0)
        for exam, values in fitted.values.items():
            self.assertTrue((values <= cohort / sizes[exam] + 1e-9).all())

    def test_linear_parameter_count_keeps_gsat_and_tongce_tails_free(self):
        exams = ["gsat", "tongce", "zhikao"]
        self.assertEqual(pool.linear_degrees(exams, 2, ("zhikao",)), 5)
        self.assertEqual(pool.linear_degrees(exams, 2), 6)
        self.assertEqual(pool.linear_degrees(exams, 3, ("zhikao",)), 8)


SMALL, MIDDLE, LARGE = complement.VOCATIONAL
SIZES = {"gsat": 126_287.0, "zhikao": 38_053.0,
         SMALL: 9_593.0, MIDDLE: 46_132.0, LARGE: 27_192.0}


class TestComplement(unittest.TestCase):
    """The fitted densities have to stack into a population somebody could be."""

    def observations(self):
        return [
            ("gsat", 0.10, MIDDLE, 0.20, 3.0),
            ("gsat", 0.20, "zhikao", 0.25, 2.0),
            (MIDDLE, 0.30, "zhikao", 0.35, 1.0),
            ("gsat", 0.50, LARGE, 0.60, 4.0),
            ("gsat", 0.40, SMALL, 0.45, 2.0),
        ]

    def test_overlap_shrinks_the_cohort_below_the_taker_counts(self):
        both = complement.cohort_size(SIZES, 0.0)
        vocational = sum(SIZES[exam] for exam in complement.VOCATIONAL)
        self.assertAlmostEqual(both, SIZES["gsat"] + vocational)
        self.assertAlmostEqual(complement.cohort_size(SIZES, 0.25), both / 1.25)
        with self.assertRaises(ValueError):
            complement.cohort_size(SIZES, -0.1)

    def test_no_overlap_leaves_the_pair_no_slack(self):
        # The floor and the taker counts pin the sum exactly when nobody sits both.
        fitted, _ = complement.fit(self.observations(), SIZES, 3, overlap=0.0)
        np.testing.assert_allclose(complement.cover(fitted), 1.0, atol=1e-6)

    def test_overlap_is_the_only_slack_the_floor_leaves(self):
        for overlap in (0.02, 0.05, 0.2):
            fitted, _ = complement.fit(self.observations(), SIZES, 3,
                                       overlap=overlap)
            cover = complement.cover(fitted)
            self.assertGreaterEqual(cover.min(), 1.0 - 1e-6, "the floor holds")
            # Every density integrates to its taker count, so however the fit
            # spends the slack it averages exactly 1 + overlap over the axis.
            weights = complement.trapezoid_weights(len(cover))
            self.assertAlmostEqual(float(weights @ cover) / (len(cover) - 1),
                                   1.0 + overlap, places=6)

    def test_no_exam_holds_more_people_than_the_cohort(self):
        fitted, _ = complement.fit(self.observations(), SIZES, 4, overlap=0.1)
        for exam in fitted.exams:
            self.assertLessEqual(float((fitted.values[exam] * SIZES[exam]).max()),
                                 fitted.cohort + 1e-6)

    def test_normalisations_hold(self):
        fitted, _ = complement.fit(self.observations(), SIZES, 3, overlap=0.05)
        for exam in fitted.exams:
            self.assertAlmostEqual(float(fitted.masses(exam).sum()), 1.0, places=7)

    def test_nested_keeps_zhikao_under_gsat(self):
        fitted, _ = complement.fit(self.observations(), SIZES, 3, nested=True)
        self.assertTrue((fitted.values["zhikao"] * SIZES["zhikao"]
                         <= fitted.values["gsat"] * SIZES["gsat"] + 1e-6).all())

    def test_recovers_a_planted_population(self):
        # Thresholds generated from a known pool have to lead back to it.
        sizes = {"gsat": 120_000.0, "zhikao": 40_000.0,
                 SMALL: 10_000.0, MIDDLE: 45_000.0, LARGE: 25_000.0}
        planted = pool.LinearAbilityPool(
            {"gsat": [4 / 3, 2 / 3, 4 / 3, 2 / 3],
             "zhikao": [0.2, 0.8, 1.6, 1.0],
             SMALL: [0.2, 1.8, 0.2, 1.8],
             MIDDLE: [0.6, 1.4, 0.6, 1.4],
             LARGE: [0.44, 1.56, 0.44, 1.56]},
            sizes,
        )
        observations = [
            (left, top, right, matching_top(planted, left, top, right), 1.0)
            for left, right in [(v, "gsat") for v in complement.VOCATIONAL]
            + [(v, "zhikao") for v in complement.VOCATIONAL] + [("gsat", "zhikao")]
            for top in (0.05, 0.15, 0.3, 0.5, 0.7, 0.85, 0.95)
        ]
        fitted, mae = complement.fit(observations, sizes, 3, overlap=0.05,
                                     nested=False)
        self.assertLess(mae, 0.5)
        for exam in fitted.exams:
            np.testing.assert_allclose(fitted.values[exam], planted.values[exam],
                                       atol=0.05)

    def test_degrees_drop_one_normalisation_per_exam(self):
        exams = len(complement.EXAMS)
        self.assertEqual(complement.degrees(3), 3 * exams)
        self.assertEqual(complement.degrees(1), exams)
        with self.assertRaises(ValueError):
            complement.degrees(0)

    def test_rejects_missing_taker_counts(self):
        with self.assertRaisesRegex(ValueError, "missing observed taker counts"):
            complement.fit(self.observations(), {"gsat": 10, "tongce": 5}, 2)


def matching_top(built, exam_a, top_a, exam_b):
    """The top fraction of `exam_b` sitting at the same ability as `exam_a`'s."""
    ability = built.ability(exam_a, top_a)
    tops = np.linspace(0.0, 1.0, 200001)
    return float(tops[np.argmin(np.abs(built.abilities(exam_b, tops) - ability))])


class TestVocationalPools(unittest.TestCase):
    """A 統測 bar is a percentile inside the 群 that sat its 數學 paper."""

    def row(self, **fields):
        got = {"year": pool_fit.YEAR, "path": "tech", "group": "機械群"}
        got.update(fields)
        return got

    def test_a_tech_row_reads_against_the_pool_that_sat_its_paper(self):
        self.assertEqual(pool_fit.exam_of(self.row()), tcte.math_pool("機械群"))
        self.assertNotEqual(pool_fit.exam_of(self.row(group="商業與管理群")),
                            pool_fit.exam_of(self.row()))

    def test_a_class_suffix_lands_in_the_same_pool_as_its_group(self):
        self.assertEqual(pool_fit.exam_of(self.row(group="電機與電子群資電類")),
                         pool_fit.exam_of(self.row(group="電機與電子群電機類")))

    def test_another_year_carries_no_bar(self):
        self.assertIsNone(pool_fit.exam_of(self.row(year="109")))

    def test_the_academic_paths_still_name_their_exam(self):
        for path, exam in (("uac", "zhikao"), ("star", "gsat"),
                           ("star_eight", "gsat"), ("apply", "gsat")):
            self.assertEqual(pool_fit.exam_of(self.row(path=path)), exam)

    def test_taker_counts_split_the_vocational_exam_into_its_pools(self):
        counts = pool_fit.taker_counts()
        self.assertNotIn("tongce", counts)
        self.assertTrue(set(complement.EXAMS) <= set(counts))
        papers = pool_fit.subject_counts(pool_fit.YEAR)["tongce"]
        self.assertAlmostEqual(sum(counts[e] for e in complement.VOCATIONAL),
                               papers[tcte.MATH], places=6)

    def test_a_pool_is_read_on_the_measurement_its_exam_sets(self):
        for exam in complement.VOCATIONAL:
            self.assertEqual(complement.measure(exam), complement.MEASURE)
        self.assertEqual(complement.measure("gsat"), "gsat")


class TestPlotCommand(unittest.TestCase):
    def test_main_wires_observations_counts_fit_and_draw(self):
        observations = [("a", 0.1, "b", 0.2, 1.0)]
        fitted = pool.AbilityPool({"a": [0.5, 0.5], "b": [0.5, 0.5]}, 2)
        with mock.patch.object(pool_fit, "observations",
                               return_value=([], observations)):
            with mock.patch.object(pool_fit, "taker_counts",
                                   return_value={"a": 10, "b": 20}):
                with mock.patch.object(pool_fit, "fit_pool",
                                       return_value=(fitted, 1.5)) as fit:
                    with mock.patch.object(pool_plot, "draw",
                                           return_value="figure.png") as draw:
                        pool_plot.main()
        fit.assert_called_once_with(observations, {"a": 10, "b": 20})
        draw.assert_called_once()


class TestDirectCommand(unittest.TestCase):
    @pytest.mark.slow
    def test_fit_script_runs_from_its_file_path(self):
        got = subprocess.run(
            [sys.executable, os.path.join(ROOT, "pool", "fit.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        self.assertEqual(got.returncode, 0, got.stderr)
        self.assertIn("matched threshold pairs", got.stdout)
        self.assertIn("wrote", got.stdout)


if __name__ == "__main__":
    unittest.main()
