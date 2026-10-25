"""Catalog payload extraction and recovery of unmapped archive ranges."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union
import xml.etree.ElementTree as ET

from .archive import ArchiveReader
from .common import AuditRecord, ExtractionStats, Terminal, TRAILER_SIZE
from .paths import OutputManager


class PayloadExtractor:
    """Extract each payload range as a complete in-memory byte string."""

    def __init__(
        self,
        archive: ArchiveReader,
        output: OutputManager,
        logger,
        try_path_reconstruct: bool = True,
        extract_unmapped: bool = True,
        stats: Optional[ExtractionStats] = None,
        audit_failed: Optional[List[AuditRecord]] = None,
        audit_missed: Optional[List[Dict[str, Union[str, int]]]] = None,
    ) -> None:
        self.archive = archive
        self.output = output
        self.logger = logger
        self.try_path_reconstruct = try_path_reconstruct
        self.extract_unmapped_enabled = extract_unmapped
        self.stats = stats if stats is not None else ExtractionStats()
        self.audit_failed = audit_failed if audit_failed is not None else []
        self.audit_missed = audit_missed if audit_missed is not None else []
        self.used_ranges = archive.used_ranges
        self.root: Optional[ET.Element] = None

    def extract_stream(
        self, target_rel_path: str, offset: int, length: int, is_missed: bool = False
    ) -> bool:
        if length <= 0:
            return False
        if offset < 0 or offset > self.archive.total_size or length > self.archive.total_size - offset:
            reason = (
                f"Archive range is out of bounds: offset={offset}, length={length}, "
                f"archive_size={self.archive.total_size}"
            )
            self._record_failure(target_rel_path, offset, length, reason, is_missed)
            self.logger.error("Invalid range for %s: %s", target_rel_path, reason)
            return False

        self.used_ranges.append((offset, length))
        try:
            payload = self.archive.read_bytes(offset, length)
            if not payload or not any(payload):
                if not is_missed:
                    self.stats.skipped_null += 1
                return False
            destination = self.output.write_bytes(target_rel_path, payload)
            if not is_missed:
                self.stats.extracted += 1
            self.logger.debug(
                "Saved %s (%s bytes)",
                destination.relative_to(self.output.output_dir),
                f"{length:,}",
            )
            return True
        except Exception as exc:
            self.logger.error("Failed extracting %s: %s", target_rel_path, exc)
            self._record_failure(target_rel_path, offset, length, str(exc), is_missed)
            return False

    def _record_failure(
        self, path: str, offset: int, length: int, reason: str, is_missed: bool
    ) -> None:
        if is_missed:
            self.stats.missed_failed += 1
        else:
            self.stats.failed += 1
        self.audit_failed.append(
            AuditRecord(path=path, offset=offset, length=length, reason=reason, is_unmapped=is_missed)
        )

    def _render_progress(self, current: int, total: int, filename: str, debug: bool) -> None:
        if debug or not Terminal.enabled() or total == 0:
            return
        bar_length = 26
        ratio = current / total
        filled = int(bar_length * ratio)
        bar = (
            f"{Terminal.GREEN}{'━' * filled}"
            f"{Terminal.DIM}{'─' * (bar_length - filled)}{Terminal.RESET}"
        )
        shortened = filename[:21] + ".." if len(filename) > 23 else filename.ljust(23)
        sys.stdout.write(
            f"\r\x1b[K{Terminal.CYAN}⠸{Terminal.RESET} [{bar}] "
            f"{ratio * 100:5.1f}% ({current}/{total}) "
            f"{Terminal.DIM}{shortened}{Terminal.RESET}"
        )
        sys.stdout.flush()

    def process_items(
        self,
        root: Optional[ET.Element],
        try_path_reconstruct: bool,
        resolve_cg_path: Callable[[str], str],
        debug: bool = False,
    ) -> None:
        self.root = root
        if root is None:
            return
        items = root.findall("BackupItem")
        self.stats.total_items = len(items)
        self.logger.info("Processing %s catalog entries...", len(items))

        for index, item in enumerate(items, start=1):
            category = item.get("Category", "UNKNOWN")
            display_name = category
            if category == "APPLICATION":
                for app in item.findall("APPLICATION"):
                    try:
                        raw_name = app.get("FileName") or app.get("Name") or "unknown.apk"
                        clean_name = Path(raw_name.replace("\\", "/")).name
                        display_name = f"app/{clean_name}"
                        self.extract_stream(
                            display_name,
                            int(app.get("StartOffset", "0")),
                            int(app.get("DataSize", "0")),
                        )
                    except (ValueError, TypeError) as exc:
                        self.logger.error("Skipping malformed application entry: %s", exc)
                        self.stats.failed += 1
            else:
                try:
                    file_name = item.get("FileName", "")
                    destination_name = f"{category}-{file_name}".rstrip("-")
                    if "_CG_" in category and try_path_reconstruct:
                        destination_name = f"media/{resolve_cg_path(category).lstrip('/')}"
                    else:
                        destination_name = f"records/{destination_name}"
                    display_name = destination_name
                    self.extract_stream(
                        destination_name,
                        int(item.get("StartOffset", "0")),
                        int(item.get("DataSize", "0")),
                    )
                except (ValueError, TypeError) as exc:
                    self.logger.error("Skipping malformed catalog entry [%s]: %s", category, exc)
                    self.stats.failed += 1
            self._render_progress(index, len(items), display_name, debug)

        if not debug and Terminal.enabled() and items:
            sys.stdout.write("\r\x1b[K")
            sys.stdout.flush()

    def extract_unmapped_regions(self, enabled: Optional[bool] = None) -> None:
        if enabled is None:
            enabled = self.extract_unmapped_enabled
        if not enabled:
            self.logger.info("Skipping unmapped-range recovery.")
            return

        self.logger.info("Scanning for unmapped archive ranges...")
        tail_end = max(0, self.archive.total_size - TRAILER_SIZE)
        merged: List[Tuple[int, int]] = []
        for start, length in sorted(self.used_ranges):
            end = start + length
            start = max(0, start)
            end = min(tail_end, end)
            if start >= end:
                continue
            if not merged or start > merged[-1][1]:
                merged.append((start, end))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))

        cursor = 0
        for start, end in merged:
            if start > cursor:
                length = start - cursor
                name = f"unmapped/block_0x{cursor:08X}_0x{start - 1:08X}.bin"
                if self.extract_stream(name, cursor, length, is_missed=True):
                    self.stats.missed_blocks += 1
                    self.audit_missed.append({"name": name, "size": length})
            cursor = max(cursor, end)

        if cursor < tail_end:
            length = tail_end - cursor
            name = f"unmapped/block_0x{cursor:08X}_0x{tail_end - 1:08X}.bin"
            if self.extract_stream(name, cursor, length, is_missed=True):
                self.stats.missed_blocks += 1
                self.audit_missed.append({"name": name, "size": length})
