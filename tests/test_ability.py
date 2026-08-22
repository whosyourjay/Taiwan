"""Tests for scoring departments by the ability their thresholds imply."""

import unittest

import numpy as np

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


class TestStar(unittest.TestCase):
    """繁星 holds two floors, and the harder one is taken."""

    def star(self, gpa, gates, seats=20):
        return row("star", seats, class_pct=100.0 - gpa, xuece_gates=gates)

    def test_the_class_rank_needs_no_curve(self):
        scored = ability.read([self.star(5.0, {})], STRAIGHT)
        _, exam, level, _ = scored[0]
        self.assertEqual(exam, ability.STAR)
        self.assertAlmostEqual(level, 0.95)

    def test_the_harder_of_the_two_floors_wins(self):
        # Class rank 0.60 against a 學測 gate at the 80th percentile.
        scored = ability.read([self.star(40.0, {"stem": 80.0})], STRAIGHT)
        self.assertAlmostEqual(scored[0][2], 0.80)

    def test_the_class_rank_wins_when_it_binds_harder(self):
        scored = ability.read([self.star(5.0, {"stem": 40.0})], STRAIGHT)
        self.assertAlmostEqual(scored[0][2], 0.95)

    def test_the_strictest_subject_family_sets_the_gate(self):
        scored = ability.read(
            [self.star(50.0, {"stem": 60.0, "language": 88.0})], STRAIGHT)
        self.assertAlmostEqual(scored[0][2], 0.88)

    def test_繁星_scores_apart_from_the_學測_paths(self):
        scored = ability.read([self.star(5.0, {}, seats=100),
                               row("apply", 100, cohort_top=0.5)], STRAIGHT)
        got = ability.table(scored, ("school", "dept"),
                            ("gsat", ability.STAR))[0]
        self.assertAlmostEqual(got[ability.STAR], 95.0)
        self.assertAlmostEqual(got["gsat"], 50.0)
        self.assertAlmostEqual(got["ability"], 72.5)

    def test_第八類_keeps_its_own_output_column(self):
        ordinary = self.star(5.0, {}, seats=100)
        eighth = self.star(2.0, {}, seats=20)
        eighth["path"] = "star_eight"
        scored = ability.read([ordinary, eighth], STRAIGHT)
        got = ability.table(scored, ("school", "dept"),
                            (ability.STAR, ability.STAR_EIGHT))[0]
        self.assertAlmostEqual(got[ability.STAR], 95.0)
        self.assertAlmostEqual(got[ability.STAR_EIGHT], 98.0)
        self.assertAlmostEqual(got["ability"], 95.5)


class TestTable(unittest.TestCase):
    def scored(self):
        return ability.read([row("uac", 100, ceec_percentile=0.9),
                             row("apply", 100, cohort_top=0.2)], STRAIGHT)

    def test_two_exams_average_by_seats_and_report_their_gap(self):
        got = ability.table(self.scored(), ("school", "dept"), EXAMS)
        self.assertEqual(len(got), 1)
        self.assertAlmostEqual(got[0]["ability"], 85.0)
        self.assertAlmostEqual(got[0]["spread"], 10.0)
        self.assertEqual(got[0]["exams"], 2)
        self.assertAlmostEqual(got[0]["zhikao"], 90.0)
        self.assertAlmostEqual(got[0]["gsat"], 80.0)

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
        moment, weight = ability.collect(scored, ("school",))
        got = weight[("A大學",)]
        self.assertAlmostEqual(got["all"], 100.0)
        self.assertAlmostEqual(got["zhikao"], 30.0)
        self.assertAlmostEqual(got["gsat"], 70.0)
        # 個申's bar clears the top 20%, so it enters the curve at 0.8.
        self.assertAlmostEqual(moment[("A大學",)]["all"], 0.9 * 30 + 0.8 * 70)


if __name__ == "__main__":
    unittest.main()
