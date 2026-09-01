"""Annual ranking-panel interpolation and quota regressions."""

import random
import unittest

from rank import annual


def scored(year, seats, ability, route="uac", school="甲大學", dept="甲學系"):
    return {
        "year": str(year), "school": school, "dept": dept, "path": route,
        "seats": seats, "score": ability,
    }


class TestAnnualPanel(unittest.TestCase):
    def test_missing_middle_year_is_interpolated(self):
        rows = [scored(108, 10, 20, "apply"), scored(110, 30, 40, "apply")]
        found = annual.build(rows, quotas=[], seat_rows=rows, totals=[], uac_seats=[])
        middle = next(row for row in found if row["year"] == 109)
        self.assertEqual((middle["seats"], middle["ability"]), (20.0, 30.0))
        self.assertEqual(middle["seats_method"], "interpolated:108,110")

    def test_official_quota_keeps_routes_without_readable_cutoffs(self):
        quota = {
            "year": "115", "school": "國立臺灣大學", "dept": "國際企業學系",
            "total": "89", "uac": "31", "star": "8", "apply": "49",
            "tech": "0",
        }
        rows = [scored(114, 30, 95, school="國立臺灣大學", dept="國際企業學系")]
        seats = rows + [
            scored(114, 7, 0, "star", "國立臺灣大學", "國際企業學系"),
            scored(114, 10, 0, "apply", "國立臺灣大學", "國際企業學系"),
        ]
        found = annual.build(rows, quotas=[quota], seat_rows=seats, totals=[],
                             uac_seats=[])
        current = {row["route"]: row for row in found if row["year"] == 115}
        self.assertEqual({route: row["seats"] for route, row in current.items()},
                         {"uac": 31.0, "star": 8.0, "apply": 49.0})
        self.assertTrue(all(row["ability"] == 95.0 for row in current.values()))
        ranked = annual.aggregate(found, ("school", "dept"))[0]
        self.assertEqual(ranked["seats_avg"], 67.5)

    def test_current_school_retains_the_name_used_that_year(self):
        quota = {
            "year": "115", "school": "國立陽明交通大學", "dept": "電機工程學系",
            "total": "20", "uac": "20", "star": "0", "apply": "0",
            "tech": "0",
        }
        rows = [scored(110, 20, 90, school="國立交通大學", dept="電機工程學系")]
        found = annual.build(rows, quotas=[quota], seat_rows=rows, totals=[],
                             uac_seats=[])
        old = next(row for row in found if row["year"] == 110)
        self.assertEqual(old["school"], "國立陽明交通大學")
        self.assertEqual(old["school_year_name"], "國立交通大學")

    def test_quota_groups_are_summed_after_department_normalization(self):
        rows = [scored(114, 20, 70)]
        quotas = [
            {"year": "115", "school": "甲大學", "dept": "甲學系甲組",
             "total": "10", "uac": "10", "star": "0", "apply": "0", "tech": "0"},
            {"year": "115", "school": "甲大學", "dept": "甲學系乙組",
             "total": "20", "uac": "20", "star": "0", "apply": "0", "tech": "0"},
        ]
        found = annual.build(rows, quotas=quotas, seat_rows=rows, totals=[],
                             uac_seats=[])
        current = next(row for row in found if row["year"] == 115)
        self.assertEqual(current["seats"], 30.0)

    def test_current_star_quota_uses_the_latest_star_category(self):
        rows = [scored(108, 8, 90, "star"), scored(114, 2, 95, "star_eight")]
        quota = {"year": "115", "school": "甲大學", "dept": "甲學系",
                 "total": "2", "uac": "0", "star": "2", "apply": "0", "tech": "0"}
        found = annual.build(rows, quotas=[quota], seat_rows=rows, totals=[],
                             uac_seats=[])
        current = {row["route"]: row["seats"]
                   for row in found if row["year"] == 115}
        self.assertEqual(current, {"star": 0.0, "star_eight": 2.0})

    def test_post_return_uac_seats_replace_quota_without_double_counting(self):
        quota = {
            "year": "115", "school": "國立臺灣大學", "dept": "國際企業學系",
            "total": "88", "uac": "31", "star": "8", "apply": "49",
            "tech": "0",
        }
        counts = [
            {"year": "115", "school": "國立臺灣大學", "dept": "國際企業學系A組",
             "seats": "8"},
            {"year": "115", "school": "國立臺灣大學", "dept": "國際企業學系B組",
             "seats": "24"},
        ]
        rows = [scored(114, 32, 95, school="國立臺灣大學",
                       dept="國際企業學系")]
        found = annual.build(rows, quotas=[quota], seat_rows=rows, totals=[],
                             uac_seats=counts)
        current = {row["route"]: row for row in found if row["year"] == 115}
        self.assertEqual({route: row["seats"] for route, row in current.items()},
                         {"uac": 32.0, "star": 8.0, "apply": 48.0})
        self.assertEqual(current["uac"]["seats_method"], "uac_post_return")
        self.assertIn("uac_return_estimate", current["apply"]["seats_method"])

    def test_capacity_does_not_replace_completed_year_admissions(self):
        rows = [scored(114, 20, 90)]
        capacity = [{
            "year": "114", "school": "甲大學", "dept": "甲學系", "seats": "30",
        }]
        found = annual.build(rows, quotas=[], seat_rows=rows, totals=[],
                             uac_seats=capacity)
        current = next(row for row in found if row["year"] == 114)
        self.assertEqual(current["seats"], 20.0)
        self.assertEqual(current["seats_method"], "observed")

    def test_interpolation_stays_on_the_line(self):
        rng = random.Random(20260901)
        for _ in range(100):
            left = rng.randint(90, 110)
            right = left + rng.randint(2, 10)
            year = rng.randint(left + 1, right - 1)
            low, high = rng.uniform(0, 100), rng.uniform(0, 100)
            value, sources = annual.estimate({left: low, right: high}, year)
            expected = low + (year - left) * (high - low) / (right - left)
            self.assertAlmostEqual(value, expected)
            self.assertEqual(sources, f"{left},{right}")


if __name__ == "__main__":
    unittest.main()
