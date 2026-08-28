import csv
import glob
import os
import random
import re
import subprocess
import unittest

from lib.paths import data_path, path, source_path
from parse.star import value

TSV = data_path("star-cutoffs.tsv")
# Each PDF costs a pdftotext subprocess, so re-read a few per run instead of all
# 88. Unseeded, so successive runs cover different files. PDFS=99 to sweep them.
PDFS = int(os.environ.get("PDFS", 6))

# Values read off the PDFs by eye.
SPOT = {
    ("110", "00101", "one2seven"): {
        "college": "國立臺灣大學", "dept": "中國文學系",
        "quota": "6", "admitted": "6", "gpa_r1": "3.0", "gpa_r2": "6.0",
        "gates": "國文頂標13 英文前標12 數學前標9 社會前標12",
    },
    # Admitted nobody in round 1, so only round 2 sets a standard.
    ("110", "00108", "one2seven"): {
        "dept": "戲劇學系", "gpa_r1": "", "gpa_r2": "2.0",
        "r1_n": "0", "r2_n": "2", "tiebreak_r1": "",
    },
    # 校系名稱 wrapped off the code row and had to be rebuilt from neighbours.
    ("110", "00634", "one2seven"): {
        "college": "國立政治大學",
        "dept": "東南亞語言與文化學士學位學程(印尼文組)",
        "quota": "2", "admitted": "2", "gpa_r2": "6.0",
    },
    # In old PDFs, round counts can sit on the department row rather than the
    # 在校學業 row carrying the percentile standards.
    ("108", "00213", "one2seven"): {
        "dept": "華語文教學系應用華語文學組", "admitted": "8",
        "r1_n": "7", "r2_n": "1",
    },
    # 第八類學群 screens to twice the quota rather than admitting.
    ("110", "00159", "eight"): {
        "college": "國立臺灣大學", "dept": "醫學系",
        "quota": "12", "admitted": "24", "gpa_r1": "3.0",
    },
    ("111", "01301", "one2seven"): {"college": "國立陽明交通大學"},
}


def rows():
    with open(TSV, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def num(s):
    return int(s) if s.isdigit() else 0


class TestStar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows()

    def test_one_row_per_dept_in_pdf(self):
        """Every 校系代碼 line in the raw text becomes exactly one row."""
        found = sorted(glob.glob(source_path("star", "*.pdf")))
        for pdf in random.sample(found, min(PDFS, len(found))):
            year, code, group = os.path.basename(pdf)[:-4].split("-")
            txt = subprocess.run(["pdftotext", "-layout", pdf, "-"],
                                 capture_output=True, text=True).stdout
            want = len(re.findall(r"^\s*\d{5}\s+\S", txt, re.M))
            got = sum(1 for r in self.rows
                      if (r["year"], r["college_code"], r["group"]) == (year, code, group))
            self.assertEqual(want, got, os.path.basename(pdf))

    def test_rounds_sum_to_admitted(self):
        for r in self.rows:
            self.assertEqual(num(r["admitted"]), num(r["r1_n"]) + num(r["r2_n"]),
                             f"{r['year']} {r['college']} {r['dept']}")

    def test_every_admitted_dept_has_a_percentile(self):
        for r in self.rows:
            if num(r["admitted"]) == 0:
                continue
            self.assertTrue(r["gpa_r1"] or r["gpa_r2"],
                            f"{r['year']} {r['college']} {r['dept']}")

    def test_percentiles_are_in_range(self):
        for r in self.rows:
            for k in ("gpa_r1", "gpa_r2", "gpa"):
                if r[k]:
                    self.assertTrue(0 < float(r[k]) <= 100, f"{r[k]} in {r['dept']}")

    def test_same_score_marker_is_not_part_of_percentile(self):
        self.assertEqual(value("1%＊"), 1.0)

    def test_names_are_never_blank(self):
        for r in self.rows:
            self.assertTrue(r["dept"].strip(), f"{r['year']} {r['dept_code']}")
            self.assertTrue(r["college"].strip(), r["college_code"])

    def test_keys_are_unique(self):
        keys = [(r["year"], r["group"], r["dept_code"], r["dept"]) for r in self.rows]
        self.assertEqual(len(keys), len(set(keys)))

    def test_spot_values(self):
        by_key = {(r["year"], r["dept_code"], r["group"]): r for r in self.rows}
        for key, want in SPOT.items():
            got = by_key.get(key)
            self.assertIsNotNone(got, key)
            for field, v in want.items():
                self.assertEqual(got[field], v, f"{key} {field}")


if __name__ == "__main__":
    unittest.main()
