"""Regressions for UAC's post-return seat workbook."""

import os
import unittest

from parse import uac_seats


class TestUacSeats(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.by_year = {}
        for source in uac_seats.source_files():
            year = os.path.basename(source).split("-", 1)[0]
            cls.by_year[year] = uac_seats.checked(*uac_seats.rows(source, year))

    def test_codes_and_total_survive_excel(self):
        self.assertEqual(self.by_year["115"][0]["code"], "0001")
        totals = {year: sum(row["seats"] for row in rows)
                  for year, rows in self.by_year.items()}
        self.assertEqual(totals, {
            "107": 40263, "108": 34576, "109": 33278,
            "110": 36327, "111": 39350, "112": 42479,
            "113": 37264, "114": 33381, "115": 32494,
        })

    def test_ntu_international_business_groups_sum_to_32(self):
        seats = sum(row["seats"] for row in self.by_year["115"]
                    if row["school"] == "國立臺灣大學"
                    and row["dept"].startswith("國際企業學系"))
        self.assertEqual(seats, 32)


if __name__ == "__main__":
    unittest.main()
