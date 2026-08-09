"""Tests for repairing OCR'd 個人申請 department names."""

import unittest

from parse.apply import snap


class TestSnap(unittest.TestCase):
    def test_ignores_latin_prefix_before_matching_a_department(self):
        got = snap("kaX外眾術史學", {"藝術史學系", "應用音樂學系"})
        self.assertEqual(got, "藝術史學系")


if __name__ == "__main__":
    unittest.main()
