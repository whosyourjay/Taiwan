"""Regressions for UAC's post-return seat workbook."""

import unittest

from lib.paths import source_path
from parse import uac_seats


class TestUacSeats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = uac_seats.checked(*uac_seats.rows(
            source_path(uac_seats.SOURCE)))

    def test_codes_and_total_survive_excel(self):
        self.assertEqual(self.rows[0]["code"], "0001")
        self.assertEqual(sum(row["seats"] for row in self.rows), 32494)

    def test_ntu_international_business_groups_sum_to_32(self):
        seats = sum(row["seats"] for row in self.rows
                    if row["school"] == "國立臺灣大學"
                    and row["dept"].startswith("國際企業學系"))
        self.assertEqual(seats, 32)


if __name__ == "__main__":
    unittest.main()
