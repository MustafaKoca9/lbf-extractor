"""Optional command-line interface for the library."""
from __future__ import annotations

import argparse
import logging
import math
import sys
import traceback

from .common import ColoredFormatter, LOGGER_NAME, __version__
from .core import LBFExtractor


def _positive_finite_mib(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number of MiB") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise argparse.ArgumentTypeError("must be a finite number greater than zero")
    return parsed


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lbf-extractor",
        description=f"LG Mobile Switch backup inspector v{__version__}",
    )
    parser.add_argument("file", help="Path to the primary .lbf file")
    parser.add_argument("-o", "--output", default="./export", help="Output directory")
    parser.add_argument(
        "--chunk-size-mib",
        type=_positive_finite_mib,
        default=1.0,
        metavar="MIB",
        help="Streaming chunk size in MiB (default: 1)",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Write metadata reports without extracting payload files",
    )
    parser.add_argument("--no-path-reconstruct", action="store_true")
    header_group = parser.add_mutually_exclusive_group()
    header_group.add_argument("--force-new", action="store_true")
    header_group.add_argument("--force-old", action="store_true")
    parser.add_argument("--split-lbf-first", action="store_true")
    parser.add_argument("--no-unmapped", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--log", metavar="FILE")
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv=None) -> int:
    args = build_cli_parser().parse_args(argv)
    logger = logging.getLogger(f"{LOGGER_NAME}.cli")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG if args.debug else logging.INFO)
    handler.setFormatter(ColoredFormatter())
    logger.addHandler(handler)

    try:
        chunk_size = max(1, int(args.chunk_size_mib * 1024 * 1024))
        with LBFExtractor(
            file_path=args.file,
            output_dir=args.output,
            try_path_reconstruct=not args.no_path_reconstruct,
            force_new_header=args.force_new,
            force_old_header=args.force_old,
            split_lbf_first=args.split_lbf_first,
            overwrite=args.overwrite,
            extract_unmapped=not args.no_unmapped,
            debug=args.debug,
            log_file=args.log,
            chunk_size=chunk_size,
            extract_files=not args.metadata_only,
        ) as extractor:
            extractor.execute()
        return 0
    except KeyboardInterrupt:
        print("Aborted by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        logger.critical("Fatal termination: %s", exc)
        if args.debug:
            traceback.print_exc()
        return 1
    finally:
        logger.removeHandler(handler)
        handler.close()


if __name__ == "__main__":
    raise SystemExit(main())
