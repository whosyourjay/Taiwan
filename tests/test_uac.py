"""Admission-source loader regressions."""

import unittest

from rank import uac


class TestApplicationGroup(unittest.TestCase):
    def test_raw_group_survives_department_normalisation(self):
        row = {"dept": "法律學系司法組"}
        uac.identify_department(row)
        self.assertEqual(row["dept"], "法律學系")
        self.assertEqual(row["application_group"], "法律學系司法組")


class TestStar(unittest.TestCase):
    def test_eighth_group_keeps_quota_and_screen_count_separate(self):
        rows = list(uac.load_star("eight"))
        ntu_medicine = next(r for r in rows if r["year"] == "110"
                            and r["school"] == "國立臺灣大學"
                            and r["dept"] == "醫學系")
        self.assertEqual(ntu_medicine["path"], "star_eight")
        self.assertEqual(ntu_medicine["screened"], 24)
        self.assertEqual(ntu_medicine["seats"], 12)

    def test_binding_gates_remain_separate_subject_bars(self):
        class Cohort:
            @staticmethod
            def binding_gates(year, gates):
                return [("國文", 0.3), ("英文", 0.1), ("自然", 0.2)]

        row = next(iter(uac.load_star(cohort=Cohort())))
        self.assertEqual(row["xuece_tops"], [0.3, 0.1, 0.2])


if __name__ == "__main__":
    unittest.main()
