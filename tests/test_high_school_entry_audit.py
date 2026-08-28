"""Regression tests for the high-school entry-report audit."""

import ssl
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fetch import high_school_entry_audit as audit


class TestOfficialDirectoryCompatibility(unittest.TestCase):
    def test_allows_verified_legacy_certificate_chains(self):
        self.assertFalse(
            audit.SSL_CONTEXT.verify_flags & ssl.VERIFY_X509_STRICT
        )


class TestWarmRun(unittest.TestCase):
    def test_complete_outputs_prevent_directory_and_site_requests(self):
        with tempfile.TemporaryDirectory() as directory:
            coverage = Path(directory) / "coverage.tsv"
            candidates = Path(directory) / "candidates.tsv"
            coverage.write_text(
                "reachable\tdiscovery\tsearch_results\tcandidate_documents\n"
                "1\tnss\t2\t1\n", encoding="utf-8"
            )
            candidates.write_text("document_url\nhttps://example/a.pdf\n",
                                  encoding="utf-8")
            args = audit.arguments([
                "--coverage", str(coverage),
                "--candidates", str(candidates),
            ])
            with mock.patch.object(
                    audit, "directory_rows",
                    side_effect=AssertionError("warm run contacted the network")):
                audit.run(args)

    def test_cold_run_defaults_to_four_workers(self):
        self.assertEqual(audit.arguments([]).workers, 4)


class TestNSSAttachments(unittest.TestCase):
    def test_accepts_list_valued_attachment_urls(self):
        result = {"data": {
            "content": [
                "<p>one</p>",
                '<a href="/uploads/third.pdf">三年成果</a>',
            ],
            "ext": [{"name": "成果.pdf", "url": [
                "/uploads/first.pdf", "/uploads/second.pdf"
            ]}],
        }}
        links = audit.links_from_result(result, "https://school.example")
        self.assertEqual(
            [link[2] for link in links],
            [
                "https://school.example/uploads/first.pdf",
                "https://school.example/uploads/second.pdf",
                "https://school.example/uploads/third.pdf",
            ],
        )
        self.assertEqual(links[2][1], "三年成果")

    def test_flattens_cms_whitespace_for_tsv(self):
        self.assertEqual(audit.clean_field("first\r\nsecond\tthird"),
                         "first second third")


if __name__ == "__main__":
    unittest.main()
