import unittest
from lbf_extractor import LBFExtractor, extract_archive
from lbf_extractor.cli import build_cli_parser

class CoreTests(unittest.TestCase):
    def test_padding(self):
        self.assertEqual(LBFExtractor.strip_pkcs7(b"data\x04\x04\x04\x04"), b"data")
        self.assertEqual(LBFExtractor.strip_pkcs7(b"data\x02\x03"), b"data\x02\x03")
        self.assertEqual(LBFExtractor.strip_pkcs7(b""), b"")
    def test_chunk_validation(self):
        with self.assertRaisesRegex(ValueError, "positive"):
            LBFExtractor("backup.lbf", chunk_size=0)
    def test_api(self):
        self.assertTrue(callable(extract_archive))
    def test_cli_metadata_option(self):
        args = build_cli_parser().parse_args(["backup.lbf", "--chunk-size-mib", "4", "--metadata-only"])
        self.assertEqual(args.chunk_size_mib, 4)
        self.assertTrue(args.metadata_only)

if __name__ == "__main__":
    unittest.main()
