"""The static visual report stays self-contained and data-backed."""

import tempfile
import unittest
from pathlib import Path

from pages import report


class TestReportData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = report.page_data(include_curves=False)

    def test_payload_uses_current_ability_outputs(self):
        self.assertGreater(len(self.data["universities"]), 100)
        self.assertGreater(len(self.data["departments"]), 2_000)
        self.assertGreater(self.data["metrics"]["seats"], 100_000)

    def test_destination_censoring_survives_into_the_report(self):
        by_type = {}
        for row in self.data["destinations"]:
            by_type[row["type"]] = by_type.get(row["type"], 0) + row["students"]
        self.assertEqual(by_type["university"], 675)
        self.assertEqual(sum(by_type.values()), 784)

    def test_current_school_names_keep_their_predecessors(self):
        nycu = next(row for row in self.data["universities"]
                    if row["school"] == "國立陽明交通大學")
        self.assertIn("國立交通大學", nycu["former"])


class TestReportPage(unittest.TestCase):
    def test_render_is_dark_self_contained_and_has_jump_navigation(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.html"
            report.render({"sample": "資料"}, output)
            page = output.read_text(encoding="utf-8")
        self.assertIn('data-theme="dark"', page)
        self.assertIn('href="#programs"', page)
        self.assertIn('id="page-data"', page)
        self.assertIn('"sample":"資料"', page)
        self.assertNotIn("__CSS__", page)
        self.assertNotIn("__JS__", page)
        self.assertNotIn("https://", page)


if __name__ == "__main__":
    unittest.main()
