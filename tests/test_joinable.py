"""Tests for joining validated admission rows to UAC departments."""

import unittest

from rank import uac


class TestJoinable(unittest.TestCase):
    def setUp(self):
        self.known = {("110", "甲大學", "環境與食品安全檢驗學士學位學程")}

    def test_accepts_a_clear_application_ocr_repair(self):
        row = {
            "year": "110",
            "school": "甲大學",
            "dept": "壞境與食品安全檢驗學士學位學程",
            "path": "apply",
        }
        self.assertEqual(uac.joinable([row], self.known), [row])
        self.assertEqual(row["dept"], "環境與食品安全檢驗學士學位學程")

    def test_never_fuzzy_matches_a_text_source(self):
        row = {
            "year": "110",
            "school": "甲大學",
            "dept": "壞境與食品安全檢驗學士學位學程",
            "path": "star",
        }
        self.assertEqual(uac.joinable([row], self.known), [])

    def test_rejects_an_ambiguous_ocr_repair(self):
        candidates = {"甲學系": "甲學系", "乙學系": "乙學系"}
        self.assertIsNone(uac.ocr_department("壞學系", candidates))


if __name__ == "__main__":
    unittest.main()
