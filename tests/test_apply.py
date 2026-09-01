"""Tests for repairing OCR'd 個人申請 department names."""

import unittest

from parse.apply import refresh_names, repair_code_names, snap


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

    def test_same_year_program_code_overrides_a_wrong_ocr_name(self):
        rows = [{
            "year": "110", "college_code": "001", "dept_code": "001202",
            "dept": "社會舉銷",
        }]
        names = {("110", "001", "00120"): "國際企業學系"}
        self.assertEqual(repair_code_names(rows, names), 1)
        self.assertEqual(rows[0]["dept"], "國際企業學系")


if __name__ == "__main__":
    unittest.main()
