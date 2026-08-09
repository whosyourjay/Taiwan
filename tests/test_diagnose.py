import unittest

import diagnose


class TestColumnWidth(unittest.TestCase):
    """star_eight overran an eight-wide field and glued itself to star."""

    def test_every_path_name_fits_its_column(self):
        for path in diagnose.PATHS:
            self.assertLess(len(path), diagnose.COLUMN, path)

    def test_the_header_names_stay_apart(self):
        head = "".join(f"{path:>{diagnose.COLUMN}}" for path in diagnose.PATHS)
        self.assertEqual(len(head), diagnose.COLUMN * len(diagnose.PATHS))
        for path in diagnose.PATHS:
            self.assertIn(f" {path}", head)


class TestScaleEndpoints(unittest.TestCase):
    def rows(self):
        return [{"year": "110", "path": "uac", "pct": 0.2, "score": 12.0},
                {"year": "110", "path": "uac", "pct": 0.9, "score": 95.0},
                {"year": "110", "path": "uac", "pct": 0.5, "score": 50.0},
                {"year": "109", "path": "uac", "pct": 0.1, "score": 3.0}]

    def test_it_reports_where_each_end_of_a_path_lands(self):
        got = diagnose.scale_endpoints(self.rows(), "110", "score")
        self.assertEqual(got["uac"], (0.2, 0.9, 12.0, 95.0))

    def test_a_path_with_one_row_that_year_has_no_span(self):
        self.assertNotIn("uac", diagnose.scale_endpoints(self.rows(), "109", "score"))


if __name__ == "__main__":
    unittest.main()
