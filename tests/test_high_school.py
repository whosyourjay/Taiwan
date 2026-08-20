"""Tests for high-school university-destination reports."""

import random
import unittest

from fetch import high_school as fetcher
from lib.paths import source_path
from parse import high_school


def report(university_lines):
    return f"""
    北一女中 110 學年度畢業生大學校系錄取人數統計表(111.8.12)
      學校名稱
      (列出錄取 10 人以上學校)
{university_lines}
 其他(國內學校)                3
 國內學校小計                 25
 國外大學
 (列出錄取 3 人以上國家/地區)
 美國                          2
 中國                          1
 香港                          1
 其他(國外大學)                1
 國外學校小計                   5
 國內外學校總計                30
 110 高三應屆畢業生總人數       31
    二、北一女中 110 學年度畢業生大學錄取管道人數統計表(111.8.12)
    """


class TestFetch(unittest.TestCase):
    def test_110_source_is_official_handbook(self):
        source = fetcher.SOURCES["110"]
        self.assertEqual(source["high_school"], "臺北市立第一女子高級中學")
        self.assertIn("fg.tp.edu.tw", source["url"])
        self.assertTrue(source["url"].endswith(".pdf"))


class TestParser(unittest.TestCase):
    def test_preserves_named_and_censored_destinations(self):
        text = report(" 國立甲大學                 12\n 私立乙大學                 10")
        rows = high_school.parse_text(text, "某高中")
        by_name = {row["destination"]: row for row in rows}
        self.assertEqual(by_name["國立甲大學"]["students"], 12)
        self.assertEqual(by_name["其他(國內學校)"]["destination_type"],
                         "domestic_other")
        self.assertEqual(by_name["美國"]["destination_type"], "foreign_country")
        self.assertEqual(sum(row["students"] for row in rows), 30)
        domestic = [r for r in rows if not r["destination_type"].startswith("foreign")]
        foreign = [r for r in rows if r["destination_type"].startswith("foreign")]
        self.assertTrue(all(row["reporting_floor"] == 10 for row in domestic))
        self.assertTrue(all(row["reporting_floor"] == 3 for row in foreign))
        self.assertTrue(all(row["graduates"] == 31 for row in rows))

    def test_random_column_spacing(self):
        rng = random.Random(20260809)
        for _ in range(100):
            left = " " * rng.randrange(0, 6)
            gap = " " * rng.randrange(2, 20)
            lines = f"{left}國立甲大學{gap}12\n{left}私立乙大學{gap}10"
            rows = high_school.parse_text(report(lines), "某高中")
            universities = [r for r in rows if r["destination_type"] == "university"]
            self.assertEqual([r["students"] for r in universities], [12, 10])

    def test_rejects_a_broken_subtotal(self):
        text = report(" 國立甲大學                 11\n 私立乙大學                 10")
        with self.assertRaisesRegex(ValueError, "domestic rows"):
            high_school.parse_text(text, "某高中")


class TestOfficialReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = fetcher.SOURCES["110"]
        cls.rows = high_school.parse({
            **source,
            "path": source_path("high-school", source["filename"]),
        })

    def test_spot_values(self):
        universities = {
            row["destination"]: row["students"]
            for row in self.rows
            if row["destination_type"] == "university"
        }
        self.assertEqual(universities["國立臺灣大學"], 267)
        self.assertEqual(universities["國立政治大學"], 80)
        self.assertEqual(universities["臺北醫學大學"], 41)
        self.assertEqual(sum(universities.values()), 675)

    def test_accounts_for_every_reported_destination(self):
        self.assertEqual(sum(row["students"] for row in self.rows), 784)
        self.assertEqual({row["graduates"] for row in self.rows}, {793})


if __name__ == "__main__":
    unittest.main()
