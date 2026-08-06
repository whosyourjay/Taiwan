import random
import unittest

import rank_uac


def rows(scores):
    """scores maps (school, dept) -> {year: norm}, all with equal seats."""
    return [
        {"school": s, "dept": d, "year": y, "norm": n, "seats": 10}
        for (s, d), years in scores.items()
        for y, n in years.items()
    ]


class TestLevelYears(unittest.TestCase):
    def test_removes_a_planted_shift(self):
        shift = {"108": 0.10, "109": 0.0, "110": -0.05}
        base = {("A", "x"): 0.8, ("A", "y"): 0.6, ("B", "x"): 0.4}
        data = rows({k: {y: v + s for y, s in shift.items()} for k, v in base.items()})
        rank_uac.level_years(data)
        # Recovered up to a common offset, since leveling recentres on the grand mean.
        offset = sum(shift.values()) / len(shift)
        for row in data:
            self.assertAlmostEqual(row["adj"] - offset, base[(row["school"], row["dept"])])

    def test_ignores_departments_missing_a_year(self):
        """A department absent in the easy year must not drag that year's mean."""
        data = rows(
            {
                ("A", "x"): {"108": 0.9, "109": 0.8},
                ("A", "y"): {"108": 0.7, "109": 0.6},
                ("B", "z"): {"109": 0.1},
            }
        )
        effect = rank_uac.level_years(data)
        self.assertAlmostEqual(effect["108"] - effect["109"], 0.1)

    def test_fuzz_shift_is_recovered(self):
        rng = random.Random(0)
        for _ in range(200):
            years = [str(y) for y in range(108, 108 + rng.randint(2, 7))]
            shift = {y: rng.uniform(-0.2, 0.2) for y in years}
            base = {("S%d" % i, "d"): rng.random() for i in range(rng.randint(2, 6))}
            data = rows({k: {y: v + shift[y] for y in years} for k, v in base.items()})
            rank_uac.level_years(data)
            spread = {r["year"]: r["adj"] - base[(r["school"], r["dept"])] for r in data}
            self.assertAlmostEqual(max(spread.values()), min(spread.values()))


if __name__ == "__main__":
    unittest.main()
