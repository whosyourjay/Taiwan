"""Tests for scoring departments by the ability their thresholds imply."""

import unittest

import numpy as np
from scipy.stats import norm

from pool import ability

EXAMS = ("gsat", "zhikao")
STRAIGHT = {exam: (lambda bottom: bottom) for exam in EXAMS}


def row(path, seats, dept="電機系", school="A大學", **extra):
    got = {"year": "110", "path": path, "school": school, "dept": dept,
           "application_group": f"{dept}甲組", "seats": seats}
    got.update(extra)
    return got


class TestRead(unittest.TestCase):
    def test_a_bar_is_read_through_its_own_exam_curve(self):
        # 指考 top 10% enters the curve at the 90th percentile from the bottom.
        scored = ability.read([row("uac", 10, ceec_percentile=0.9)], STRAIGHT)
        self.assertEqual(len(scored), 1)
        _, exam, level, seats = scored[0]
        self.assertEqual(exam, "zhikao")
        self.assertAlmostEqual(level, 0.9)
        self.assertAlmostEqual(seats, 10.0)

    def test_a_row_with_no_bar_is_skipped(self):
        # 分發 publishes a few departments with no usable cutoff.
        self.assertEqual(ability.read([row("uac", 40)], STRAIGHT), [])

    def test_繁星_with_neither_floor_is_skipped(self):
        self.assertEqual(ability.read([row("star", 40)], STRAIGHT), [])

    def test_another_year_is_skipped(self):
        old = row("uac", 10, ceec_percentile=0.9)
        old["year"] = "109"
        self.assertEqual(ability.read([old], STRAIGHT), [])

    def test_an_exam_with_no_curve_is_skipped(self):
        scored = ability.read([row("uac", 10, ceec_percentile=0.9)],
                              {"gsat": lambda bottom: bottom})
        self.assertEqual(scored, [])

    def test_a_curve_running_past_the_ends_is_held_to_a_percentile(self):
        wild = {"zhikao": lambda bottom: 4.0 * bottom - 1.5}
        levels = [level for _, _, level, _ in ability.read(
            [row("uac", 10, ceec_percentile=0.99),
             row("uac", 10, ceec_percentile=0.01, dept="乙系")], wild)]
        self.assertEqual(levels, [1.0, 0.0])


SCHOOLS = [-0.6, -0.2, 0.0, 0.4, 1.1, 1.9]
SPREAD = 0.75
COHORT = 200_000
# The school means in these tests are already on the exam-sitting scale.
SITTING = 1.0


class TestStar(unittest.TestCase):
    """繁星 holds two floors, and the reading is the ability they leave standing."""

    def star(self, gpa, tops, seats=20):
        return row("star", seats, class_pct=100.0 - gpa, xuece_tops=tops)

    def level(self, gpa, tops, schools=None):
        scored = ability.read([self.star(gpa, tops)], STRAIGHT,
                              SCHOOLS if schools is None else schools, COHORT,
                              SITTING)
        return scored[0][2]

    def test_one_school_averages_its_own_top_slice(self):
        # A lone average school: the top 5% of a N(0, 0.75) sit at 0.75*φ/0.05.
        want = norm.cdf(SPREAD * norm.pdf(norm.isf(0.05)) / 0.05)
        self.assertAlmostEqual(self.level(5.0, [], [0.0]), want, places=3)

    def test_a_class_rank_beats_the_share_it_names(self):
        # The top 5% of every school outrank far more than 95% of the country,
        # because each school's slice is taken from its own middle upwards.
        self.assertGreater(self.level(5.0, []), 0.95)

    def test_a_gate_never_lowers_the_reading(self):
        for gpa in (2.0, 20.0, 60.0):
            self.assertGreaterEqual(self.level(gpa, [0.30]) + 1e-12,
                                    self.level(gpa, []))

    def test_every_subject_bar_counts_not_just_the_strictest(self):
        # Asking the same bar of a second subject is a real extra demand, so it
        # has to read higher than asking it of one.
        one = self.level(50.0, [0.12])
        two = self.level(50.0, [0.12, 0.12])
        self.assertGreater(two, one)

    def test_a_gate_above_every_school_still_reads(self):
        self.assertLessEqual(self.level(50.0, [0.001]), 1.0)

    def test_繁星_scores_apart_from_the_學測_paths(self):
        scored = ability.read([self.star(5.0, [], seats=100),
                               row("apply", 100, cohort_top=0.5)],
                              STRAIGHT, SCHOOLS, COHORT, SITTING)
        got = ability.table(scored, ("school", "dept"),
                            ("gsat", ability.STAR))[0]
        self.assertAlmostEqual(got["gsat"], 50.0)
        self.assertGreater(got[ability.STAR], got["gsat"])
        self.assertAlmostEqual(got["ability"],
                               (got[ability.STAR] + got["gsat"]) / 2, places=1)

    def test_第八類_keeps_its_own_output_column(self):
        ordinary = self.star(5.0, [], seats=100)
        eighth = self.star(2.0, [], seats=20)
        eighth["path"] = "star_eight"
        got = ability.table(ability.read([ordinary, eighth], STRAIGHT,
                                         SCHOOLS, COHORT, SITTING),
                            ("school", "dept"),
                            (ability.STAR, ability.STAR_EIGHT))[0]
        self.assertGreater(got[ability.STAR_EIGHT], got[ability.STAR])
        self.assertAlmostEqual(
            got["ability"],
            (100 * got[ability.STAR] + 20 * got[ability.STAR_EIGHT]) / 120,
            places=1)


class TestStarBugs(unittest.TestCase):
    """Cases that were read wrongly before, kept so they cannot come back."""

    def star(self, gpa, tops, seats=20, dept="電機系"):
        return row("star", seats, dept=dept, class_pct=100.0 - gpa,
                   xuece_tops=tops)

    def level(self, gpa, tops, schools=None):
        scored = ability.read([self.star(gpa, tops)], STRAIGHT,
                              SCHOOLS if schools is None else schools, COHORT,
                              SITTING)
        return scored[0][2] if scored else None

    def test_a_wall_of_gates_is_rarer_than_its_strictest_bar(self):
        # 臺大醫's four 頂標 bars were read as the single hardest of them.
        grid = np.linspace(-4.5, 4.5, 600)
        tops = [0.181, 0.141, 0.11, 0.14]
        passing = ability.gate_pass(tops, grid)
        share = float((passing * norm.pdf(grid) * (grid[1] - grid[0])).sum())
        self.assertLess(share, min(tops))
        self.assertGreater(share, float(np.prod(tops)))

    def test_harder_gates_read_higher_at_the_same_rank(self):
        # 頂標 of four subjects against 前標 of four, which had tied.
        loose = self.level(3.0, [0.25, 0.25, 0.25, 0.25])
        tight = self.level(3.0, [0.12, 0.12, 0.12, 0.12])
        self.assertGreater(tight, loose)

    def test_a_school_too_small_cannot_fill_a_one_percent_bar(self):
        # Sixty graduates round their best student to 2%, so 1% reaches nobody.
        self.assertIsNone(self.level(1.0, [], [(0.0, 60)]))
        self.assertIsNotNone(self.level(1.0, [], [(0.0, 300)]))

    def test_a_served_department_leaves_less_for_the_next(self):
        alone = self.level(20.0, [])
        strict = self.star(1.0, [], seats=4000)
        loose = self.star(20.0, [], seats=20, dept="乙系")
        scored = ability.read([strict, loose], STRAIGHT, SCHOOLS, COHORT,
                              SITTING)
        after = [got for r, _, got, _ in scored if r["dept"] == "乙系"][0]
        self.assertLess(after, alone)

    def test_第八類_draws_on_its_screen_not_its_quota(self):
        def trailing(screen):
            strict = self.star(1.0, [], seats=200)
            strict["path"] = "star_eight"
            strict["screened"] = screen
            loose = self.star(20.0, [], seats=20, dept="乙系")
            scored = ability.read([strict, loose], STRAIGHT, SCHOOLS, COHORT,
                                  SITTING)
            return [got for r, _, got, _ in scored if r["dept"] == "乙系"][0]
        self.assertLess(trailing(8000), trailing(200))


class TestStarFuzz(unittest.TestCase):
    """Whatever the schools look like, the two bars can only push one way."""

    def schools(self, rng):
        return rng.normal(0.4, 0.7, size=rng.integers(2, 40))

    def test_a_stricter_rank_reads_higher(self):
        rng = np.random.default_rng(11)
        for _ in range(200):
            means, gate = self.schools(rng), rng.normal(0, 1)
            loose, tight = sorted(rng.uniform(0.01, 0.9, size=2))[::-1]
            strict = ability.qualifying_ability(tight, gate, means, SPREAD)
            slack = ability.qualifying_ability(loose, gate, means, SPREAD)
            self.assertGreaterEqual(strict + 1e-9, slack)

    def test_a_stricter_gate_reads_higher(self):
        rng = np.random.default_rng(12)
        for _ in range(200):
            means, rank = self.schools(rng), rng.uniform(0.01, 0.9)
            low, high = sorted(rng.normal(0, 1.2, size=2))
            self.assertGreaterEqual(
                ability.qualifying_ability(rank, high, means, SPREAD) + 1e-9,
                ability.qualifying_ability(rank, low, means, SPREAD))

    def test_the_margin_sits_under_the_mean_of_the_same_group(self):
        # The alternative reading takes the bottom of the eligible group, so it
        # can only fall below the average of everyone standing in it.
        rng = np.random.default_rng(14)
        for _ in range(200):
            means, rank = self.schools(rng), rng.uniform(0.02, 0.9)
            gate = rng.normal(0, 1)
            wanted, cohort = rng.integers(5, 400), 200_000
            margin = ability.marginal_ability(rank, gate, means, SPREAD,
                                              wanted, cohort)
            mean = ability.qualifying_ability(rank, gate, means, SPREAD)
            self.assertLessEqual(margin, mean + 1e-9)

    def test_a_bigger_intake_reaches_higher(self):
        # Wanting more people can only push the margin up, because the group is
        # filled from the bottom of what qualifies.
        rng = np.random.default_rng(15)
        for _ in range(200):
            means, rank = self.schools(rng), rng.uniform(0.02, 0.9)
            small, big = sorted(rng.integers(5, 4000, size=2))
            few = ability.marginal_ability(rank, None, means, SPREAD,
                                           small, 200_000)
            many = ability.marginal_ability(rank, None, means, SPREAD,
                                            big, 200_000)
            self.assertGreaterEqual(many + 1e-9, few)

    def test_the_reading_never_sits_below_the_weakest_school(self):
        rng = np.random.default_rng(13)
        for _ in range(200):
            means = self.schools(rng)
            got = ability.qualifying_ability(rng.uniform(0.01, 0.9), None,
                                             means, SPREAD)
            self.assertGreater(got, means.min())


class TestTable(unittest.TestCase):
    def scored(self):
        return ability.read([row("uac", 100, ceec_percentile=0.9),
                             row("apply", 100, cohort_top=0.2)], STRAIGHT)

    def test_two_exams_average_by_seats_and_report_their_gap(self):
        got = ability.table(self.scored(), ("school", "dept"), EXAMS)
        self.assertEqual(len(got), 1)
        self.assertAlmostEqual(got[0]["ability"], 85.0)
        self.assertAlmostEqual(got[0]["spread"], 10.0)
        self.assertEqual(got[0]["years"], 1)
        self.assertAlmostEqual(got[0]["zhikao"], 90.0)
        self.assertAlmostEqual(got[0]["gsat"], 80.0)

    def test_years_counts_distinct_source_years(self):
        first = row("uac", 10)
        second = row("uac", 10)
        second["year"] = "111"
        scored = [(first, "zhikao", 0.8, 10),
                  (second, "zhikao", 0.9, 10)]
        got = ability.table(scored, ("school", "dept"), EXAMS)
        self.assertEqual(got[0]["years"], 2)

    def test_final_schools_use_current_name_and_keep_predecessors(self):
        yang_ming = row("uac", 10, school="國立陽明大學")
        chiao_tung = row("uac", 30, school="國立交通大學")
        scored = [(yang_ming, "zhikao", 0.8, 10),
                  (chiao_tung, "zhikao", 0.9, 30)]
        got = ability.table(scored, ("school",), EXAMS)[0]
        self.assertEqual(got["school"], "國立陽明交通大學")
        self.assertEqual(got["school_en"],
                         "National Yang Ming Chiao Tung University")
        self.assertEqual(got["former_schools"], "國立陽明大學 | 國立交通大學")
        self.assertAlmostEqual(got["ability"], 87.5)
        self.assertAlmostEqual(got["seats"], 40.0)

    def test_generated_names_follow_each_chinese_name(self):
        english = {"A大學": "University A", "電機系": "Electrical Engineering"}
        got = ability.table(self.scored(), ("school", "dept"), EXAMS, english)[0]
        self.assertEqual(list(got)[:5],
                         ["rank", "school", "school_en", "dept", "dept_en"])
        self.assertEqual(got["school_en"], "University A")
        self.assertEqual(got["dept_en"], "Electrical Engineering")

    def test_the_bigger_path_pulls_the_average(self):
        scored = ability.read([row("uac", 300, ceec_percentile=0.9),
                               row("apply", 100, cohort_top=0.2)], STRAIGHT)
        got = ability.table(scored, ("school", "dept"), EXAMS)
        self.assertAlmostEqual(got[0]["ability"], 87.5)

    def test_one_exam_leaves_the_gap_blank(self):
        scored = ability.read([row("uac", 100, ceec_percentile=0.9)], STRAIGHT)
        got = ability.table(scored, ("school", "dept"), EXAMS)
        self.assertEqual(got[0]["spread"], "")
        self.assertEqual(got[0]["gsat"], "")

    def test_ranks_run_from_the_ablest_down(self):
        scored = ability.read([
            row("uac", 10, ceec_percentile=0.5),
            row("uac", 10, dept="乙系", ceec_percentile=0.9),
            row("uac", 10, dept="丙系", ceec_percentile=0.7),
        ], STRAIGHT)
        got = ability.table(scored, ("school", "dept"), EXAMS)
        self.assertEqual([r["rank"] for r in got], [1, 2, 3])
        self.assertEqual([r["dept"] for r in got], ["乙系", "丙系", "電機系"])

    def test_groups_of_one_department_are_scored_apart(self):
        scored = ability.read([row("uac", 10, ceec_percentile=0.9),
                               row("uac", 10, ceec_percentile=0.4)], STRAIGHT)
        scored[1][0]["application_group"] = "電機系乙組"
        got = ability.table(scored, ("school", "dept", "application_group"), EXAMS)
        self.assertEqual([r["ability"] for r in got], [90.0, 40.0])
        merged = ability.table(scored, ("school", "dept"), EXAMS)
        self.assertAlmostEqual(merged[0]["ability"], 65.0)


class TestPoolRatio(unittest.TestCase):
    def test_candidates_above_the_bar_use_cumulative_scaled_seats(self):
        rows = [
            {"school": "A大學", "ability": 99.0},
            {"school": "B大學", "ability": 98.0},
        ]
        got = ability.add_pool_ratios(rows, {"A大學": 100, "B大學": 200}, 10_000)
        self.assertEqual(got[0]["pool_seats"], 100.0)
        self.assertEqual(got[0]["ability_pool_ratio"], 1.0)
        self.assertEqual(got[1]["ability_pool_ratio"], 0.67)

    def test_tied_schools_enter_the_denominator_together(self):
        rows = [
            {"school": "A大學", "ability": 99.0},
            {"school": "B大學", "ability": 99.0},
        ]
        got = ability.add_pool_ratios(rows, {"A大學": 40, "B大學": 60}, 10_000)
        self.assertEqual([row["ability_pool_ratio"] for row in got], [1.0, 1.0])


class TestFuzz(unittest.TestCase):
    def scored(self, rng, count):
        rows = [row("uac", float(rng.integers(1, 200)), dept=f"系{i}",
                    ceec_percentile=float(rng.uniform(0, 1)))
                for i in range(count)]
        rows += [row("apply", float(rng.integers(1, 200)), dept=f"系{i}",
                     cohort_top=float(rng.uniform(0, 1)))
                 for i in range(count)]
        return ability.read(rows, STRAIGHT)

    def test_every_score_is_a_percentile_and_ranks_are_a_permutation(self):
        rng = np.random.default_rng(20260810)
        for _ in range(200):
            got = ability.table(self.scored(rng, int(rng.integers(1, 20))),
                                ("school", "dept"), EXAMS)
            self.assertEqual(sorted(r["rank"] for r in got),
                             list(range(1, len(got) + 1)))
            for r in got:
                self.assertTrue(0.0 <= r["ability"] <= 100.0)
                self.assertLessEqual(min(r["gsat"], r["zhikao"]), r["ability"])
                self.assertGreaterEqual(max(r["gsat"], r["zhikao"]), r["ability"])
            self.assertEqual([r["ability"] for r in got],
                             sorted((r["ability"] for r in got), reverse=True))

    def test_seats_are_neither_lost_nor_invented(self):
        rng = np.random.default_rng(20260810)
        for _ in range(100):
            scored = self.scored(rng, int(rng.integers(1, 20)))
            got = ability.table(scored, ("school", "dept"), EXAMS)
            self.assertAlmostEqual(sum(r["seats"] for r in got),
                                   sum(seats for *_, seats in scored), places=6)

    def test_disagreement_is_a_gap_in_every_band_that_has_one(self):
        rng = np.random.default_rng(20260810)
        bands = ability.disagreement(self.scored(rng, 400), EXAMS)
        self.assertEqual(len(bands), 10)
        for gap in bands:
            self.assertTrue(np.isnan(gap) or 0.0 <= gap <= 1.0)


class TestCollect(unittest.TestCase):
    def test_a_key_carries_its_seats_once_overall_and_once_per_exam(self):
        scored = ability.read([row("uac", 30, ceec_percentile=0.9),
                               row("apply", 70, cohort_top=0.2)], STRAIGHT)
        moment, weight, years = ability.collect(scored, ("school",))
        got = weight[("A大學",)]
        self.assertAlmostEqual(got["all"], 100.0)
        self.assertAlmostEqual(got["zhikao"], 30.0)
        self.assertAlmostEqual(got["gsat"], 70.0)
        # 個申's bar clears the top 20%, so it enters the curve at 0.8.
        self.assertAlmostEqual(moment[("A大學",)]["all"], 0.9 * 30 + 0.8 * 70)
        self.assertEqual(years[("A大學",)], {"110"})


if __name__ == "__main__":
    unittest.main()
