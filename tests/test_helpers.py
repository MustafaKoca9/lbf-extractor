"""Unit tests for small, deterministic helpers."""

import unittest

from lbf_extractor import LBFExtractor


class PKCS7PaddingTests(unittest.TestCase):
    def test_removes_valid_pkcs7_padding(self):
        self.assertEqual(
            LBFExtractor.strip_pkcs7(b"data\x04\x04\x04\x04"),
            b"data",
        )

    def test_keeps_invalid_padding(self):
        self.assertEqual(
            LBFExtractor.strip_pkcs7(b"data\x02\x03"),
            b"data\x02\x03",
        )

    def test_empty_input(self):
        self.assertEqual(LBFExtractor.strip_pkcs7(b""), b"")

    def test_padding_larger_than_aes_block_is_preserved(self):
        self.assertEqual(LBFExtractor.strip_pkcs7(b"data\x11"), b"data\x11")


if __name__ == "__main__":
    unittest.main()
