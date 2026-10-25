import unittest

from lbf_extractor import LBFExtractor, extract_archive


class CoreTests(unittest.TestCase):
    def test_padding(self):
        self.assertEqual(LBFExtractor.strip_pkcs7(b"data\x04\x04\x04\x04"), b"data")
        self.assertEqual(LBFExtractor.strip_pkcs7(b"data\x02\x03"), b"data\x02\x03")
        self.assertEqual(LBFExtractor.strip_pkcs7(b""), b"")

    def test_api(self):
        self.assertTrue(callable(extract_archive))


if __name__ == "__main__":
    unittest.main()
