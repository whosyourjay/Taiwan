"""Tests for the ministry's per-department quota allocation."""

import unittest

import pdfplumber

from lib.paths import source_path
from parse import university_quotas as quotas


class TestQuotaBugs(unittest.TestCase):
    """Rows the layout hides: wrapped names and two-campus schools."""

    @classmethod
    def setUpClass(cls):
        with pdfplumber.open(source_path(quotas.SOURCE)) as pdf:
            cls.found = quotas.checked(quotas.rows(pdf))
        cls.by_key = {(row["school"], row["dept"]): row for row in cls.found}

    def test_a_name_wrapped_over_two_lines_reads_in_order(self):
        # The seats sit between the two halves of the name, so ordering the
        # row left to right interleaves them into 機組械工程學系...
        row = self.by_key[("國立中央大學", "機械工程學系先進材料與精密製造組")]
        self.assertEqual(row["total"], 41)

    def test_both_campuses_keep_their_own_departments(self):
        schools = {row["school"] for row in self.found}
        self.assertIn("康寧大學(臺北)", schools)

    def test_the_share_column_is_not_read_as_a_count(self):
        row = self.by_key[("國立政治大學", "歷史學系")]
        self.assertEqual(row[quotas.SHARE], "5%")

    def test_the_inside_columns_add_up_to_the_published_subtotal(self):
        for row in self.found:
            if row["total"] is None:
                self.assertTrue(all(row[name] is None for name in quotas.INSIDE),
                                f"{row['school']} {row['dept']}")
                continue
            inside = sum(row[name] or 0 for name in quotas.INSIDE)
            self.assertEqual(inside, row["total"], f"{row['school']} {row['dept']}")

    def test_apply_is_the_largest_route(self):
        seats = {name: sum(row[name] or 0 for row in self.found)
                 for name in quotas.INSIDE}
        self.assertEqual(max(seats, key=seats.get), "apply")
        self.assertGreater(seats["apply"], seats["uac"] + seats["star"])


if __name__ == "__main__":
    unittest.main()
