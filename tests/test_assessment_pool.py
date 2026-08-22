"""Tests for the Taiwan assessment-pool arithmetic."""

import unittest

from parse import assessment_pool


class TestAssessmentPool(unittest.TestCase):
    def test_track_mix_subtracts_the_estimated_intersection_once(self):
        xuece = {"total": 128600, "current": 113004, "vocational": 8712, "ordinary": 117790}
        tongce = {"current": 84463, "registered": 88310, "vocational": 80057,
                  "ordinary": 2368, "comprehensive": 4491, "other": 1394}
        overlap = assessment_pool.overlap(xuece, tongce, {"vocational": 83493,
                                                           "academic": 99664, "total": 191909})
        self.assertEqual(round(sum(overlap.values())), 12415)
        self.assertEqual(round(xuece["current"] + tongce["current"] - sum(overlap.values())),
                         185052)


if __name__ == "__main__":
    unittest.main()
