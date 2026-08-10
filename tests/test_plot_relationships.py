import unittest

import plot_relationships
import rank_uac


class TestStarPoints(unittest.TestCase):
    def test_points_keep_all_available_gate_families(self):
        model = rank_uac.ComponentModel(
            {
                "star:class": 0.0,
                "star:gate:language": 0.0,
                "star:gate:stem": 0.0,
                "uac": 0.0,
            },
            {"star:class": 1.0, "star:gate": 1.0, "uac": 1.0},
            {},
            {
                "star:class": 1.0,
                "star:gate:language": 1.0,
                "star:gate:stem": 1.0,
                "uac": 1.0,
            },
        )
        observations = [
            (("114", "S", "D"), "star:class", 60.0, 10),
            (("114", "S", "D"), "star:gate:language", 70.0, 10),
            (("114", "S", "D"), "star:gate:stem", 80.0, 10),
            (("114", "S", "D"), "uac", 50.0, 10),
        ]
        points = plot_relationships.star_points(observations, model)
        self.assertEqual(len(points), 1)
        self.assertGreater(points[0][0], 60.0)


if __name__ == "__main__":
    unittest.main()
