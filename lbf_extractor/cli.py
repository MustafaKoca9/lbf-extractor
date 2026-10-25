"""Optional command-line wrapper."""
import argparse
import logging
import sys
import traceback
from .common import LOGGER_NAME, ColoredFormatter, __version__
from .core import LBFExtractor

def build_cli_parser():
    parser = argparse.ArgumentParser(prog="lbf-extractor", description=f"LG Backup Inspector v{__version__}")
    parser.add_argument("file", help="Path to primary .lbf file")
    parser.add_argument("-o", "--output", default="./export")
    parser.add_argument("--chunk-size-mib", type=float, default=1.0, help="Streaming chunk size in MiB")
    parser.add_argument("--metadata-only", action="store_true", help="Write reports without extracting payload files")
    parser.add_argument("--no-path-reconstruct", action="store_true")
    parser.add_argument("--force-new", action="store_true")
    parser.add_argument("--force-old", action="store_true")
    parser.add_argument("--split-lbf-first", action="store_true")
    parser.add_argument("--no-unmapped", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--log", metavar="FILE")
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    return parser

def main(argv=None):
    args = build_cli_parser().parse_args(argv)
    if args.chunk_size_mib <= 0:
        print("chunk-size-mib must be positive", file=sys.stderr)
        return 2
    logger = logging.getLogger(f"{LOGGER_NAME}.cli")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG if args.debug else logging.INFO)
    handler.setFormatter(ColoredFormatter())
    logger.handlers.clear()
    logger.addHandler(handler)
    try:
        with LBFExtractor(file_path=args.file, output_dir=args.output, try_path_reconstruct=not args.no_path_reconstruct, force_new_header=args.force_new, force_old_header=args.force_old, split_lbf_first=args.split_lbf_first, overwrite=args.overwrite, extract_unmapped=not args.no_unmapped, debug=args.debug, log_file=args.log, chunk_size=max(1, int(args.chunk_size_mib * 1024 * 1024)), extract_files=not args.metadata_only) as extractor:
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

if __name__ == "__main__":
    raise SystemExit(main())
