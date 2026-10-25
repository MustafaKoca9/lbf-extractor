"""Tests for CLI argument parsing and constructor validation."""

import unittest

from lbf_extractor import LBFExtractor, build_cli_parser


class CLIParserTests(unittest.TestCase):
    def setUp(self):
        self.parser = build_cli_parser()

    def test_default_arguments(self):
        args = self.parser.parse_args(["backup.lbf"])
        self.assertEqual(args.file, "backup.lbf")
        self.assertEqual(args.output, "./export")
        self.assertFalse(args.debug)
        self.assertFalse(args.overwrite)
        self.assertFalse(args.no_unmapped)

    def test_optional_arguments(self):
        args = self.parser.parse_args(
            [
                "backup.lbf",
                "--output",
                "recovered",
                "--debug",
                "--overwrite",
                "--no-unmapped",
                "--split-lbf-first",
                "--force-new",
                "--log",
                "run.log",
            ]
        )
        self.assertEqual(args.output, "recovered")
        self.assertTrue(args.debug)
        self.assertTrue(args.overwrite)
        self.assertTrue(args.no_unmapped)
        self.assertTrue(args.split_lbf_first)
        self.assertTrue(args.force_new)
        self.assertEqual(args.log, "run.log")

    def test_header_modes_are_mutually_exclusive(self):
        with self.assertRaisesRegex(ValueError, "mutually exclusive"):
            LBFExtractor(
                "backup.lbf",
                force_new_header=True,
                force_old_header=True,
            )

    def test_non_lbf_input_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "valid .lbf archive"):
            LBFExtractor("backup.zip")


if __name__ == "__main__":
    unittest.main()
