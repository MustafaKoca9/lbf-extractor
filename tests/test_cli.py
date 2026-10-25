import unittest
from lbf_extractor.cli import build_cli_parser

class CLITests(unittest.TestCase):
    def test_defaults(self):
        args = build_cli_parser().parse_args(["backup.lbf"])
        self.assertEqual(args.output, "./export")
        self.assertEqual(args.chunk_size_mib, 1.0)

if __name__ == "__main__":
    unittest.main()
