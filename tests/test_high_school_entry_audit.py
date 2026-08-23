"""Regression tests for the high-school entry-report audit."""

import ssl
import unittest

from fetch import high_school_entry_audit as audit


class TestOfficialDirectoryCompatibility(unittest.TestCase):
    def test_allows_verified_legacy_certificate_chains(self):
        self.assertFalse(
            audit.SSL_CONTEXT.verify_flags & ssl.VERIFY_X509_STRICT
        )


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
