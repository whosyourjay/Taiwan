"""Tests for automatic high-school entry-report classification."""

import random
import unittest

from parse import high_school_entry_reports as reports


class TestClassifier(unittest.TestCase):
    def test_cap_distribution_with_random_spacing(self):
        rng = random.Random(20260823)
        bins = ("5A", "4A1B", "3A2B")
        for _ in range(100):
            spaced = ["".join(letter + " " * rng.randrange(4) for letter in value)
                      for value in bins]
            text = "新生入學情形 國中教育會考 " + " 人數 10 ".join(spaced)
            label, confidence, _ = reports.classify(text)
            self.assertEqual(label, "entrance_distribution")
            self.assertEqual(confidence, "high")

    def test_bct_percentiles_are_a_distribution(self):
        text = "新生入學情形 國中基本學力測驗成績 P5 210 P50 312 P95 398"
        label, _, evidence = reports.classify(text)
        self.assertEqual(label, "entrance_distribution")
        self.assertIn("percentiles=P5,P50,P95", evidence)

    def test_workshop_is_not_an_entrance_distribution(self):
        text = "高中優質化教師增能工作坊實施計畫，歡迎教師報名參加。"
        label, _, _ = reports.classify(text)
        self.assertEqual(label, "training_or_event")

    def test_dates_in_a_plan_are_not_score_ranges(self):
        text = ("學校經營計畫 108-112 年度工作期程，109-110 年辦理教師研習，"
                "111-112 年完成校舍整建。")
        label, _, _ = reports.classify(text)
        self.assertEqual(label, "school_plan_or_report")

    def test_metadata_selects_reports_and_opaque_files(self):
        report = {"page_title": "", "document_name": "高中優質化三年成果.pdf"}
        opaque = {"page_title": "", "document_name": "1656990300092.pdf"}
        self.assertEqual(reports.metadata_classification(report)[0],
                         "needs_content")
        self.assertEqual(reports.metadata_classification(opaque)[0],
                         "needs_content")


if __name__ == "__main__":
    unittest.main()
