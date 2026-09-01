import unittest
import gzip
import tempfile
from pathlib import Path

from lib.paths import data_path
from parse.uac import ART_MAX, max_score, pdf_text, repair_names


class TestMaxScore(unittest.TestCase):
    def test_academic_only(self):
        subjects = [("國", "1.50"), ("英", "1.25"), ("數甲", "1.25")]
        self.assertAlmostEqual(max_score("114", subjects), 60 * 4.0)
        self.assertAlmostEqual(max_score("110", subjects), 100 * 4.0)

    def test_art_keeps_its_own_scale(self):
        """術科 stays on 100 when the academic subjects move to 60."""
        subjects = [("國", "1.00"), ("英", "1.00"), ("術", "2.00")]
        self.assertAlmostEqual(max_score("114", subjects), 60 * 2 + ART_MAX * 2)
        self.assertAlmostEqual(max_score("110", subjects), 100 * 2 + ART_MAX * 2)

    def test_no_cutoff_exceeds_its_maximum(self):
        """The scale is only right if it bounds every observed cutoff."""
        import csv
        import os

        source = data_path("uac-cutoffs.tsv")
        if not os.path.exists(source):
            self.skipTest("uac-cutoffs.tsv not built")
        with open(source, encoding="utf-8") as f:
            worst = max(float(r["norm"]) for r in csv.DictReader(f, delimiter="\t"))
        self.assertLessEqual(worst, 1.0, "a cutoff exceeds its formula's maximum")


class TestPdfTextCache(unittest.TestCase):
    def test_reads_a_compressed_text_cache_without_the_pdf(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "report.pdf"
            with gzip.open(str(pdf.with_suffix(".txt")) + ".gz", "wt",
                           encoding="utf-8") as handle:
                handle.write("招生資料")
            self.assertEqual(pdf_text(str(pdf)), "招生資料")


class TestOfficialNames(unittest.TestCase):
    def test_workbook_expands_an_abbreviated_pdf_department(self):
        rows = [{
            "year": "107", "code": "0110", "school": "國立臺灣師範大學",
            "dept": "人發與家庭系家庭生活教育組",
        }]
        names = {("107", "0110"): (
            "國立臺灣師範大學", "人類發展與家庭學系家庭生活教育組",
        )}
        self.assertEqual(repair_names(rows, names), 1)
        self.assertEqual(rows[0]["dept"], "人類發展與家庭學系家庭生活教育組")


if __name__ == "__main__":
    unittest.main()
