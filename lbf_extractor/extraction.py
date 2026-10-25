"""Payload streaming, catalog traversal, and unmapped-range recovery."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from .common import AuditRecord, SecurityError, Terminal, TRAILER_SIZE


class ExtractionMixin:
    def extract_stream(
        self,
        target_rel_path: str,
        offset: int,
        length: int,
        is_missed: bool = False,
    ) -> bool:
        """Stream one archive range through a temporary file and publish it safely."""
        if length <= 0:
            return False

        if offset < 0 or offset >= self.total_size or length > self.total_size - offset:
            reason = (
                f"Archive range is out of bounds: offset={offset}, length={length}, "
                f"archive_size={self.total_size}"
            )
            self._record_failure(target_rel_path, offset, length, reason, is_missed)
            self.logger.error("Skipping invalid range for %s: %s", target_rel_path, reason)
            return False

        temporary_path: Optional[Path] = None
        try:
            destination = self.get_safe_destination(target_rel_path)
            destination.parent.mkdir(parents=True, exist_ok=True)

            # Catalog ranges should not be rediscovered as orphan data, even if
            # writing the corresponding output file later fails.
            self.used_ranges.append((offset, length))
            all_zero = True
            bytes_left = length
            cursor = offset

            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{destination.name}.",
                suffix=".part",
                dir=str(destination.parent),
                delete=False,
            ) as output:
                temporary_path = Path(output.name)
                while bytes_left > 0:
                    index = self._find_slice_index(cursor)
                    slice_start = (
                        cursor if index == 0
                        else cursor - self.part_boundaries[index - 1]
                    )
                    take = min(
                        bytes_left,
                        self.part_boundaries[index] - cursor,
                        self.chunk_size,
                    )
                    self.file_handles[index].seek(slice_start)
                    chunk = self.file_handles[index].read(take)
                    if not chunk:
                        raise OSError("Unexpected end of archive stream.")

                    if all_zero and any(chunk):
                        all_zero = False
                    written = output.write(chunk)
                    if written != len(chunk):
                        raise OSError("Short write while writing an extracted file.")

                    bytes_left -= len(chunk)
                    cursor += len(chunk)

            if all_zero:
                temporary_path.unlink(missing_ok=True)
                temporary_path = None
                if not is_missed:
                    self.stats.skipped_null += 1
                return False

            destination = self.publish_temp_file(temporary_path, destination)
            temporary_path = None

            if not is_missed:
                self.stats.extracted += 1
            self.logger.debug(
                "Saved %s (%s bytes)", destination.relative_to(self.output_dir),
                f"{length:,}",
            )
            return True

        except SecurityError as exc:
            self.logger.error("SECURITY: %s", exc)
            self._record_failure(target_rel_path, offset, length, str(exc), is_missed)
            return False
        except Exception as exc:
            self.logger.error("Failed extracting %s: %s", target_rel_path, exc)
            self._record_failure(target_rel_path, offset, length, str(exc), is_missed)
            return False
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _record_failure(
        self, path: str, offset: int, length: int, reason: str, is_missed: bool
    ) -> None:
        if is_missed:
            self.stats.missed_failed += 1
        else:
            self.stats.failed += 1
        self.audit_failed.append(
            AuditRecord(
                path=path,
                offset=offset,
                length=length,
                reason=reason,
                is_unmapped=is_missed,
            )
        )

    def _render_progress(self, current: int, total: int, filename: str) -> None:
        if self.debug or not Terminal.enabled() or total == 0:
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
            f"\\r\\x1b[K{Terminal.CYAN}⠸{Terminal.RESET} [{bar}] "
            f"{ratio * 100:5.1f}% ({current}/{total}) "
            f"{Terminal.DIM}{shortened}{Terminal.RESET}"
        )
        sys.stdout.flush()

    def process_items(self) -> None:
        if self.root is None:
            return

        items = self.root.findall("BackupItem")
        self.stats.total_items = len(items)
        self.logger.info("Processing %s catalog entries...", len(items))

        for index, item in enumerate(items, start=1):
            category = item.get("Category", "UNKNOWN")
            display_name = category
            try:
                if category == "APPLICATION":
                    apps = item.findall("APPLICATION")
                    for app in apps:
                        raw_name = app.get("FileName") or app.get("Name") or "unknown.apk"
                        clean_name = Path(raw_name.replace("\\\\", "/")).name
                        display_name = f"app/{clean_name}"
                        self.extract_stream(
                            display_name,
                            int(app.get("StartOffset", "0")),
                            int(app.get("DataSize", "0")),
                        )
                else:
                    file_name = item.get("FileName", "")
                    destination_name = f"{category}-{file_name}".rstrip("-")
                    if "_CG_" in category and self.try_path_reconstruct:
                        resolved = self.resolve_cg_path(category).lstrip("/")
                        destination_name = f"media/{resolved}"
                    else:
                        destination_name = f"records/{destination_name}"

                    display_name = destination_name
                    self.extract_stream(
                        destination_name,
                        int(item.get("StartOffset", "0")),
                        int(item.get("DataSize", "0")),
                    )
            except (ValueError, TypeError) as exc:
                self.logger.error(
                    "Skipping malformed catalog entry [%s]: %s", category, exc
                )
                self.stats.failed += 1

            self._render_progress(index, len(items), display_name)

        if not self.debug and Terminal.enabled() and items:
            sys.stdout.write("\\r\\x1b[K")
            sys.stdout.flush()

    def extract_unmapped_regions(self) -> None:
        """Recover archive ranges not covered by header/catalog reads."""
        if not self.extract_unmapped_enabled:
            self.logger.info("Skipping unmapped-range recovery (--no-unmapped).")
            return

        self.logger.info("Scanning for unmapped archive ranges...")
        tail_end = max(0, self.total_size - TRAILER_SIZE)
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
