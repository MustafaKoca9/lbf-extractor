"""Public orchestrator that composes the independent extraction components."""
from __future__ import annotations

import datetime
import logging
import platform
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional, Tuple, Union

from .archive import ArchiveReader
from .common import (
    CHUNK_SIZE,
    LOGGER_NAME,
    __author__,
    __version__,
    AuditRecord,
    ColoredFormatter,
    CorruptedArchiveError,
    ExtractionStats,
    Terminal,
)
from .diagnostics import write_metadata_report
from .extraction import PayloadExtractor
from .metadata import MetadataParser
from .paths import OutputManager
from .reporting import print_summary_box


class LBFExtractor:
    """Coordinate archive reading, metadata parsing, payload extraction, and reports."""

    def __init__(
        self,
        file_path: Union[str, Path],
        output_dir: Union[str, Path] = "./export",
        try_path_reconstruct: bool = True,
        force_new_header: bool = False,
        force_old_header: bool = False,
        split_lbf_first: bool = False,
        overwrite: bool = False,
        extract_unmapped: bool = True,
        debug: bool = False,
        log_file: Optional[Union[str, Path]] = None,
        chunk_size: int = CHUNK_SIZE,
        extract_files: bool = True,
    ) -> None:
        self.archive_path = Path(file_path).expanduser().resolve()
        if self.archive_path.suffix.lower() != ".lbf":
            raise ValueError(f"Target must have a .lbf extension: {self.archive_path}")
        if (
            not isinstance(chunk_size, int)
            or isinstance(chunk_size, bool)
            or chunk_size <= 0
        ):
            raise ValueError("chunk_size must be a positive integer number of bytes")
        if force_new_header and force_old_header:
            raise ValueError("force_new_header and force_old_header are mutually exclusive")

        self.output_dir = Path(output_dir).expanduser().resolve()
        self.try_path_reconstruct = try_path_reconstruct
        self.force_new_header = force_new_header
        self.force_old_header = force_old_header
        self.split_lbf_first = split_lbf_first
        self.overwrite = overwrite
        self.extract_unmapped_enabled = extract_unmapped
        self.extract_files_enabled = bool(extract_files)
        self.debug = debug
        self.chunk_size = chunk_size

        self.logger = self._init_logger(debug, log_file)
        self.archive = ArchiveReader(self.archive_path, split_lbf_first=split_lbf_first)
        self.output = OutputManager(self.output_dir, overwrite=overwrite)
        self.metadata = MetadataParser(self.archive, self.output, self.logger)

        self.root: Optional[ET.Element] = None
        self.common_header: Optional[ET.Element] = None
        self.stats = ExtractionStats()
        self.audit_failed: List[AuditRecord] = []
        self.audit_missed: List[Dict[str, Union[str, int]]] = []
        self.start_time: Optional[datetime.datetime] = None
        self.end_time: Optional[datetime.datetime] = None

        self.payload = PayloadExtractor(
            archive=self.archive,
            output=self.output,
            logger=self.logger,
            chunk_size=self.chunk_size,
            try_path_reconstruct=self.try_path_reconstruct,
            extract_unmapped=self.extract_unmapped_enabled,
            stats=self.stats,
            audit_failed=self.audit_failed,
            audit_missed=self.audit_missed,
        )

    def _init_logger(
        self,
        debug: bool,
        log_file: Optional[Union[str, Path]],
    ) -> logging.Logger:
        logger = logging.getLogger(f"{LOGGER_NAME}.{id(self):x}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False

        for handler in list(logger.handlers):
            logger.removeHandler(handler)
            handler.close()

        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.DEBUG if debug else logging.INFO)
        console.setFormatter(ColoredFormatter())
        logger.addHandler(console)

        if log_file:
            resolved_log = Path(log_file).expanduser().resolve()
            if resolved_log == self.archive_path:
                logger.removeHandler(console)
                console.close()
                raise ValueError("The log file must not be the archive itself.")
            try:
                file_handler = logging.FileHandler(
                    resolved_log, mode="w", encoding="utf-8"
                )
            except Exception:
                logger.removeHandler(console)
                console.close()
                raise
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)-8s] "
                    "<%(filename)s:%(lineno)d> %(message)s"
                )
            )
            logger.addHandler(file_handler)
        return logger

    @property
    def part_paths(self) -> List[Path]:
        return self.archive.part_paths

    @property
    def file_handles(self) -> List[BinaryIO]:
        return self.archive.file_handles

    @property
    def part_boundaries(self) -> List[int]:
        return self.archive.part_boundaries

    @property
    def total_size(self) -> int:
        return self.archive.total_size

    @property
    def used_ranges(self) -> List[Tuple[int, int]]:
        return self.archive.used_ranges

    @property
    def header_format(self) -> Optional[str]:
        return self.metadata.header_format

    @header_format.setter
    def header_format(self, value: Optional[str]) -> None:
        self.metadata.header_format = value

    def __enter__(self) -> "LBFExtractor":
        try:
            Terminal.init()
            self.start_time = datetime.datetime.now()
            self.output.prepare()

            if not self.output.is_empty():
                if self.overwrite:
                    self.logger.warning(
                        "Export destination is not empty; matching files may be replaced."
                    )
                else:
                    self.logger.warning(
                        "Export destination is not empty; new files will be versioned."
                    )

            self.archive.open()
            self._print_banner()
            return self
        except Exception:
            self._cleanup()
            raise

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._cleanup()
        self.end_time = datetime.datetime.now()

    def _cleanup(self) -> None:
        self.archive.close()
        for handler in list(self.logger.handlers):
            self.logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

    def _print_banner(self) -> None:
        banner = Terminal.style(
            "LG Backup Extractor (lbf-extractor)", Terminal.CYAN, Terminal.BOLD
        )
        archive_name = Terminal.style(self.archive_path.name, Terminal.BOLD)
        platform_line = Terminal.style(
            f"Platform: {platform.system()} {platform.release()} | "
            f"Python: {platform.python_version()}",
            Terminal.DIM,
        )
        print(
            f"{banner} v{__version__} by {__author__}\n"
            f"Archive: {archive_name} ({self.total_size / (1024 * 1024):,.2f} MiB "
            f"across {len(self.part_paths)} part(s))\n"
            f"{platform_line}\n"
        )

        if len(self.part_paths) > 1:
            self.logger.info("Multipart segment assembly order:")
            previous_boundary = 0
            for index, path in enumerate(self.part_paths):
                boundary = self.part_boundaries[index]
                size = boundary - previous_boundary
                previous_boundary = boundary
                self.logger.info("  [%d] %s (%s bytes)", index, path.name, f"{size:,}")

    def _parse_candidate(self, is_new: bool) -> Tuple[ET.Element, ET.Element]:
        checkpoint = len(self.archive.used_ranges)
        previous_format = self.header_format
        try:
            root = self.metadata.parse_header(is_new)
            common_header = root.find("Common")
            if common_header is None:
                raise CorruptedArchiveError(
                    "Parsed XML does not contain the required <Common> descriptor."
                )
            return root, common_header
        except Exception:
            del self.archive.used_ranges[checkpoint:]
            self.header_format = previous_format
            raise

    def execute(self) -> None:
        if not self.archive.is_open:
            raise RuntimeError("Use LBFExtractor as a context manager before execute().")

        self.metadata.check_lock_status()
        preferred_new = (
            True if self.force_new_header
            else False if self.force_old_header
            else True
        )
        can_fallback = not self.force_new_header and not self.force_old_header

        header_range_start = len(self.archive.used_ranges)
        try:
            self.root, self.common_header = self._parse_candidate(preferred_new)
        except (CorruptedArchiveError, ET.ParseError, struct.error, IndexError) as primary_error:
            if not can_fallback:
                raise
            self.logger.warning(
                "Primary header format failed (%s); trying the alternate format.",
                primary_error,
            )
            self.root, self.common_header = self._parse_candidate(not preferred_new)

        is_new_element = self.common_header.find("IsNew")
        if (
            can_fallback
            and self.header_format != "new"
            and is_new_element is not None
            and is_new_element.text == "True"
        ):
            previous_format = self.header_format
            ranges_before_realignment = len(self.archive.used_ranges)
            try:
                new_root, new_common = self._parse_candidate(True)
            except (CorruptedArchiveError, ET.ParseError, struct.error, IndexError) as exc:
                self.header_format = previous_format
                self.logger.debug("Automatic header realignment failed: %s", exc)
            else:
                # Keep only the successful header candidate's byte ranges.
                # Otherwise an abandoned header interpretation would be counted
                # as consumed during unmapped-range recovery.
                new_header_ranges = self.archive.used_ranges[ranges_before_realignment:]
                del self.archive.used_ranges[header_range_start:]
                self.archive.used_ranges.extend(new_header_ranges)
                self.root, self.common_header = new_root, new_common

        if self.header_format == "new":
            self.used_ranges.append((0, 1))

        self.stats.total_items = (
            len(self.root.findall("BackupItem")) if self.root is not None else 0
        )

        # Preserve a complete metadata record even if a payload range later
        # fails to write or is rejected by the output path policy.
        report_path = write_metadata_report(
            self.output,
            root=self.root,
            common_header=self.common_header,
            archive_path=self.archive_path,
            archive=self.archive,
            header_format=self.header_format,
            extract_files_enabled=self.extract_files_enabled,
            try_path_reconstruct=self.try_path_reconstruct,
            resolve_cg_path=self.resolve_cg_path,
        )
        self.logger.info("Metadata report written: %s", report_path)

        if self.extract_files_enabled:
            self.payload.process_items(
                root=self.root,
                try_path_reconstruct=self.try_path_reconstruct,
                resolve_cg_path=self.resolve_cg_path,
                debug=self.debug,
            )
            self.payload.extract_unmapped_regions(self.extract_unmapped_enabled)
        else:
            self.logger.info("Metadata-only mode: payload extraction is disabled.")

        self.end_time = datetime.datetime.now()
        self.print_summary_box()
        self.logger.info("Processing completed successfully.")

    # Compatibility façade: existing library callers can keep using these methods.
    def read_bytes(self, offset: int, length: int) -> bytes:
        return self.archive.read_bytes(offset, length)

    def _find_slice_index(self, offset: int) -> int:
        return self.archive._find_slice_index(offset)

    def get_safe_destination(self, virtual_path: str) -> Path:
        return self.output.get_safe_destination(virtual_path)

    def write_text_safely(self, virtual_path: str, contents: str) -> Path:
        return self.output.write_text_safely(virtual_path, contents)

    @staticmethod
    def strip_pkcs7(payload: bytes) -> bytes:
        return MetadataParser.strip_pkcs7(payload)

    def decrypt_payload(self, cipher_data: bytes) -> bytes:
        return self.metadata.decrypt_payload(cipher_data)

    def get_header_length(self, is_new: bool) -> int:
        return self.metadata.get_header_length(is_new)

    def parse_header(self, is_new: bool) -> ET.Element:
        return self.metadata.parse_header(is_new)

    def resolve_cg_path(self, category: str) -> str:
        return self.metadata.resolve_cg_path(category, self.common_header)

    def check_lock_status(self) -> bool:
        return self.metadata.check_lock_status()

    def extract_stream(
        self,
        target_rel_path: str,
        offset: int,
        length: int,
        is_missed: bool = False,
    ) -> bool:
        return self.payload.extract_stream(target_rel_path, offset, length, is_missed)

    def process_items(self) -> None:
        self.payload.process_items(
            self.root,
            self.try_path_reconstruct,
            self.resolve_cg_path,
            self.debug,
        )

    def extract_unmapped_regions(self) -> None:
        self.payload.extract_unmapped_regions(self.extract_unmapped_enabled)

    def _record_failure(
        self, path: str, offset: int, length: int, reason: str, is_missed: bool
    ) -> None:
        self.payload._record_failure(path, offset, length, reason, is_missed)

    def _render_progress(self, current: int, total: int, filename: str) -> None:
        self.payload._render_progress(current, total, filename, self.debug)

    def print_summary_box(self) -> None:
        print_summary_box(
            self.stats,
            self.audit_failed,
            self.start_time or datetime.datetime.now(),
            self.end_time or datetime.datetime.now(),
        )
