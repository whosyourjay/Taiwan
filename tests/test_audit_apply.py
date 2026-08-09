"""Tests for the 個申-to-分發 audit labels."""

import unittest

from audit_apply import classify


def row(college="甲大學", code="001001"):
    return {"year": "110", "college_code": "001", "dept_code": code, "college": college}


class TestClassify(unittest.TestCase):
    def test_does_not_call_a_blank_school_no_fenfa(self):
        status, _ = classify(row(""), set(), {}, set())
        self.assertEqual(status, "unidentified_school_png")

    def test_marks_a_school_without_uac_rows_no_fenfa(self):
        status, _ = classify(row(), set(), {}, set())
        self.assertEqual(status, "no_fenfa_school")

    def test_separates_valid_unmatched_from_unscored_png_rows(self):
        key = ("110", "001", "001001")
        schools = {("110", "甲大學")}
        self.assertEqual(classify(row(), {key}, {}, schools)[0], "unmatched_png")
        self.assertEqual(classify(row(), set(), {}, schools)[0], "unscored_png")


if __name__ == "__main__":
    unittest.main()
