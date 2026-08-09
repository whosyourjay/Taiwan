"""Tests for 四技日間部申請入學 collection and parsing."""

import random
import unittest
from unittest import mock

from fetch import tech_apply as fetcher
from parse import tech_apply


class TestFetch(unittest.TestCase):
    def test_110_official_inputs(self):
        got = fetcher.urls("110")
        self.assertTrue(got["screen"].endswith("/110/caac/repot_01.pdf"))
        self.assertTrue(got["rules"].endswith("/110/caac/110_caac_minute.xls"))


class TestScreenReport(unittest.TestCase):
    def test_uses_primary_gsat_screen_not_apcs_alternative(self):
        text = """
        101001 國立臺灣科技大學 材料科學與工程系 83.81 -- --
        101005 國立臺灣科技大學 資訊管理系 80.00 7.00 72.00
        """
        self.assertEqual(
            tech_apply.screen_cutoffs(text),
            {"101001": 83.81, "101005": 80.0},
        )

    def test_random_spacing_and_scores(self):
        rng = random.Random(20260809)
        lines, expected = [], {}
        for i in range(100):
            code = str(100000 + i)
            score = rng.randrange(0, 10_001) / 100
            spaces = " " * rng.randrange(1, 8)
            lines.append(
                f"{spaces}{code}{spaces}某科技大學{spaces}某系"
                f"{spaces}{score:.2f} -- --"
            )
            expected[code] = score
        self.assertEqual(tech_apply.screen_cutoffs("\n".join(lines)), expected)


class TestPrograms(unittest.TestCase):
    def program(self):
        return {
            "志願代碼": "101001",
            "學校": "國立臺灣科技大學",
            "系（組）、學程名稱": "材料科學與工程系",
            "招生名額": "49",
            "預計複試人數": "245",
            "國文權重": "1.00",
            "英文權重": "2.00",
            "數學權重": "2.00",
            "社會權重": "---",
            "自然權重": "2.00",
        }

    def test_formula_ignores_unselected_subjects(self):
        self.assertEqual(
            tech_apply.formula_of(self.program()),
            [("國文", 1.0), ("英文", 2.0), ("數學", 2.0), ("自然", 2.0)],
        )

    def test_random_weighted_average_round_trip(self):
        rng = random.Random(20260809)
        for _ in range(100):
            screen = rng.uniform(0, 100)
            subjects = [(str(i), rng.uniform(0.1, 3.0)) for i in range(5)]
            raw = tech_apply.raw_cutoff(screen, subjects)
            maximum = tech_apply.GSAT_MAX * sum(weight for _, weight in subjects)
            self.assertAlmostEqual(raw / maximum, screen / 100)

    def test_joins_rule_to_report_and_recovers_raw_cutoff(self):
        report = "101001 國立臺灣科技大學 材料科學與工程系 83.81 -- --"
        with mock.patch.object(tech_apply, "pdf_text", return_value=report):
            with mock.patch.object(
                tech_apply, "workbook_rows", return_value=[self.program()]
            ):
                rows, reported = tech_apply.parse_pair("report.pdf", "rules.xls", "110")
        self.assertEqual(reported, 1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["seats"], 49)
        self.assertEqual(rows[0]["screened"], 245)
        self.assertAlmostEqual(rows[0]["cutoff"], 88.0005)


if __name__ == "__main__":
    unittest.main()
