"""Extractor orchestration and public LBFExtractor class."""
from __future__ import annotations

import datetime
import logging
import platform
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional, Tuple, Union

from .archive import ArchiveMixin
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
from .extraction import ExtractionMixin
from .metadata import MetadataMixin
from .paths import PathMixin
from .reporting import ReportingMixin


class LBFExtractor(ArchiveMixin, PathMixin, MetadataMixin, ExtractionMixin, ReportingMixin):
    """Streaming inspector and extractor for segmented LG Mobile Switch archives."""

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
        self.debug = debug
        self.chunk_size = chunk_size
        self.extract_files_enabled = bool(extract_files)

        self.part_paths: List[Path] = []
        self.file_handles: List[BinaryIO] = []
        self.part_boundaries: List[int] = []
        self.total_size = 0
        self.used_ranges: List[Tuple[int, int]] = []

        self.root: Optional[ET.Element] = None
        self.common_header: Optional[ET.Element] = None
        self.header_format: Optional[str] = None

        self.stats = ExtractionStats()
        self.audit_failed: List[AuditRecord] = []
        self.audit_missed: List[Dict[str, int]] = []
        self.start_time: Optional[datetime.datetime] = None
        self.end_time: Optional[datetime.datetime] = None

        self.logger = self._init_logger(debug, log_file)

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

    def __enter__(self) -> "LBFExtractor":
        try:
            Terminal.init()
            self.start_time = datetime.datetime.now()
            self.output_dir.mkdir(parents=True, exist_ok=True)

            if any(self.output_dir.iterdir()):
                if self.overwrite:
                    self.logger.warning(
                        "Export destination is not empty; matching files may be replaced."
                    )
                else:
                    self.logger.warning(
                        "Export destination is not empty; new files will be versioned."
                    )

            self._load_archive_segments()
            self._print_banner()
            return self
        except Exception:
            self._cleanup()
            raise

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._cleanup()
        self.end_time = datetime.datetime.now()

    def _cleanup(self) -> None:
        """Close all owned file handles and logging handlers; safe to call repeatedly."""
        for handle in self.file_handles:
            try:
                handle.close()
            except OSError:
                pass
        self.file_handles.clear()

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
        root = self.parse_header(is_new)
        common_header = root.find("Common")
        if common_header is None:
            raise CorruptedArchiveError(
                "Parsed XML does not contain the required <Common> descriptor."
            )
        return root, common_header

    def execute(self) -> None:
        """Inspect metadata, optionally extract payloads, then print a summary."""
        self.check_lock_status()

        preferred_new = (
            True if self.force_new_header
            else False if self.force_old_header
            else True
        )
        can_fallback = not self.force_new_header and not self.force_old_header

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
            try:
                new_root, new_common = self._parse_candidate(True)
            except (CorruptedArchiveError, ET.ParseError, struct.error, IndexError) as exc:
                self.header_format = previous_format
                self.logger.debug("Automatic header realignment failed: %s", exc)
            else:
                self.root, self.common_header = new_root, new_common

        if self.header_format == "new":
            self.used_ranges.append((0, 1))

        if self.root is not None:
            self.stats.total_items = len(self.root.findall("BackupItem"))

        from .diagnostics import write_metadata_report

        report_path = write_metadata_report(self)
        self.logger.info("Metadata report written: %s", report_path)

        if self.extract_files_enabled:
            self.process_items()
            self.extract_unmapped_regions()
        else:
            self.logger.info("Metadata-only mode: payload extraction is disabled.")

        self.end_time = datetime.datetime.now()
        self.print_summary_box()
        self.logger.info("Processing completed successfully.")
