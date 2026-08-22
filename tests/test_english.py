"""Tests for generated English labels."""

import tempfile
import unittest
from pathlib import Path

from lib import english


class Translator:
    def translate(self, text):
        return text.replace("甲大學", "University A").replace("乙系", "Department B")


class EnglishNamesTest(unittest.TestCase):
    def test_translates_new_names_and_reuses_the_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "names.tsv"
            got = english.english_names({"甲大學", "乙系"}, path, Translator())
            self.assertEqual(got["甲大學"], "University A")
            self.assertEqual(got["乙系"], "Department B")
            self.assertEqual(english.load_cache(path), got)


if __name__ == "__main__":
    unittest.main()
