"""Tests for low-impact source-cache compression."""

import gzip
import tempfile
import unittest
from pathlib import Path

from tools import compress_text_caches


class TestCompression(unittest.TestCase):
    def test_compressed_copy_is_verified_and_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "report.txt"
            source.write_text("招生資料\n" * 100, encoding="utf-8")
            target = compress_text_caches.compress(source)
            self.assertTrue(source.exists())
            with gzip.open(target, "rt", encoding="utf-8") as handle:
                self.assertEqual(handle.read(), source.read_text(encoding="utf-8"))

    def test_half_duty_rests_for_as_long_as_it_worked(self):
        self.assertEqual(compress_text_caches.rest(3, 0.5), 3)


if __name__ == "__main__":
    unittest.main()
