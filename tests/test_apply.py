"""Tests for repairing OCR'd 個人申請 department names."""

import unittest

from parse.apply import refresh_names, snap


class TestSnap(unittest.TestCase):
    def test_ignores_latin_prefix_before_matching_a_department(self):
        got = snap("kaX外眾術史學", {"藝術史學系", "應用音樂學系"})
        self.assertEqual(got, "藝術史學系")

    def test_refresh_only_accepts_a_name_from_the_text_sources(self):
        rows = [{
            "year": "110", "college_code": "001", "college": "甲大學",
            "dept_code": "001012", "dept": "壞境與食品安全檢驗學士學位學程",
            "dept_ocr": "壞境與食品安全檢驗學士學位學程",
        }]
        readings = [("110", "001", "001012", "環境與食品安全檢驗學士學位學程")]
        changed, missing = refresh_names(
            rows, readings, {"甲大學": {"環境與食品安全檢驗學士學位學程"}}
        )
        self.assertEqual((changed, missing), (1, 0))
        self.assertEqual(rows[0]["dept"], "環境與食品安全檢驗學士學位學程")


if __name__ == "__main__":
    unittest.main()
