"""Warm fetch commands use their local corpus without network discovery."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fetch import apply, ceec, entry_quotas, star


class TestWarmFetches(unittest.TestCase):
    def test_ceec_skips_populated_exam_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for exam in ceec.INDEXES:
                target = root / exam
                target.mkdir()
                (target / "cached.xls").write_bytes(b"source")
            with mock.patch.object(ceec, "source_path",
                                   side_effect=lambda *parts: str(root.joinpath(*parts[1:]))), \
                    mock.patch.object(ceec, "year_pages",
                                      side_effect=AssertionError("network discovery")):
                ceec.main()

    def test_star_skips_a_cached_year(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "110.complete").write_text("complete\n")
            with mock.patch.object(star, "OUT", str(target)), \
                    mock.patch.object(star, "colleges",
                                      side_effect=AssertionError("network discovery")):
                star.main(["110"])

    def test_apply_skips_a_cached_year_and_preserves_its_name_table(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "110.complete").write_text("complete\n")
            (target / "110-statistics.html").write_text("cached statistics\n")
            names = target / "colleges.tsv"
            names.write_text("year\tcollege_code\tcollege\n110\t001\t甲大學\n",
                             encoding="utf-8")
            with mock.patch.object(apply, "OUT", str(target)), \
                    mock.patch.object(apply, "get",
                                      side_effect=AssertionError("network fetch")), \
                    mock.patch.object(apply, "colleges",
                                      side_effect=AssertionError("network discovery")):
                apply.main(["110"])
            self.assertIn("110\t001\t甲大學", names.read_text(encoding="utf-8"))

    def test_entry_quotas_skip_a_populated_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)
            (target / "quota.pdf").write_bytes(b"source")
            with mock.patch.object(entry_quotas.tsvio, "read_rows", return_value=[]), \
                    mock.patch.object(entry_quotas, "source_path",
                                      return_value=str(target)), \
                    mock.patch.object(entry_quotas, "district_files",
                                      side_effect=AssertionError("network discovery")):
                self.assertEqual(entry_quotas.main(), 0)


if __name__ == "__main__":
    unittest.main()
