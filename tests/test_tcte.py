import collections
import csv
import unittest

import numpy as np

from lib.paths import data_path
from parse import tcte
from pool import fit as pool_fit

PART = "專業(一)"
# 108 is the first year the papers were split and 110 the last with 數學(S).
YEARS = ("108", "109", "110")
# Published paper totals against 群 sizes, in candidates out of roughly 90,000.
SLACK = 80


def subject_counts(year):
    """Candidates in every published 統測 subject of one year."""
    return pool_fit.subject_counts(year)["tongce"]


def department_groups(year):
    """Every 群類 that admitted through 四技二專聯合登記分發 in one year."""
    with open(data_path("tech-cutoffs.tsv"), encoding="utf-8") as f:
        return sorted({row["group"] for row in csv.DictReader(f, delimiter="\t")
                       if row["year"] == year})


class TestMathPapers(unittest.TestCase):
    """The 群 to 數學 paper table is read off headcounts, so it has to add up."""

    def test_the_groups_sitting_a_paper_account_for_its_candidates(self):
        for year in YEARS:
            counts = subject_counts(year)
            known = set(counts)
            papers = collections.defaultdict(set)
            for group in department_groups(year):
                paper = tcte.PAPER_OF[tcte.group_stem(group)]
                papers[paper].add(tcte.professional_subject(group, PART, known))
            for paper, professional in papers.items():
                got = sum(counts[subject] for subject in professional)
                self.assertAlmostEqual(got, counts[paper], delta=SLACK,
                                       msg=f"{year} {paper}")

    def test_every_admitting_group_sits_a_paper(self):
        for year in ("108", "110", "114"):
            for group in department_groups(year):
                self.assertIn(tcte.math_pool(group), tcte.POOLS, group)

    def test_the_papers_partition_the_groups(self):
        seen = [group for groups in tcte.MATH_PAPERS.values() for group in groups]
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(set(tcte.PAPER_OF), set(seen))

    def test_the_pools_partition_the_papers(self):
        self.assertEqual(set(tcte.POOL_OF), set(tcte.MATH_PAPERS))
        self.assertEqual(len(tcte.POOLS), 3)

    def test_the_pools_hold_every_maths_candidate(self):
        for year in ("108", "110", "114"):
            counts = subject_counts(year)
            got = sum(counts[paper] for pool in tcte.POOLS
                      for paper in tcte.POOL_PAPERS[pool])
            self.assertAlmostEqual(got, counts[tcte.MATH], delta=1.0, msg=year)


class TestMathSubject(unittest.TestCase):
    def test_a_group_sits_its_own_paper_where_that_is_published(self):
        known = set(subject_counts("110"))
        self.assertEqual(tcte.math_subject("機械群", known), "數學(C)")
        self.assertEqual(tcte.math_subject("藝術群影視類", known), "數學(S)")

    def test_a_retired_paper_falls_back_to_the_rest_of_its_pool(self):
        known = set(subject_counts("114"))
        self.assertNotIn("數學(S)", known)
        self.assertEqual(tcte.math_subject("藝術群影視類", known), "數學(A)")

    def test_an_unknown_group_falls_back_to_the_pooled_paper(self):
        self.assertEqual(tcte.math_subject("無此群", {tcte.MATH}), tcte.MATH)

    def test_it_gives_up_where_no_maths_is_published(self):
        self.assertIsNone(tcte.math_subject("機械群", {"國文"}))

    def test_a_pool_is_labelled_by_the_paper_that_defines_it(self):
        self.assertEqual([tcte.pool_label(p) for p in tcte.POOLS],
                         ["統測(A)", "統測(B)", "統測(C)"])


class TestFuzz(unittest.TestCase):
    def test_a_class_suffix_never_changes_the_paper(self):
        rng = np.random.default_rng(20260810)
        groups = [g for g in tcte.PAPER_OF if g.endswith("群")]
        letters = list("甲乙丙資電影視幼保生活應用")
        for _ in range(200):
            group = str(rng.choice(groups))
            tail = "".join(rng.choice(letters, rng.integers(1, 4))) + "類"
            self.assertEqual(tcte.math_pool(group + tail), tcte.math_pool(group))

    def test_every_group_lands_in_exactly_one_pool(self):
        pools = collections.Counter()
        for group in tcte.PAPER_OF:
            pools[tcte.math_pool(group)] += 1
        self.assertEqual(sum(pools.values()), len(tcte.PAPER_OF))
        self.assertEqual(set(pools), set(tcte.POOLS))


if __name__ == "__main__":
    unittest.main()
