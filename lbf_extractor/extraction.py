import sys
from pathlib import Path
from typing import Optional,List,Tuple
from .common import CHUNK_SIZE,AuditRecord,SecurityError,Terminal
class ExtractionMixin:
    def extract_stream(
        self,
        target_rel_path: str,
        offset: int,
        length: int,
        is_missed: bool = False,
    ) -> bool:
        """Stream a logical range from the archive to ``target_rel_path``.

        Skips zero-entropy padding blocks. Records every failure (including
        unmapped/forensic blocks) in ``audit_failed``.
        """
        if length <= 0:
            return False

        out_file: Optional[Path] = None
        try:
            out_file = self.get_safe_destination(target_rel_path)
            out_file.parent.mkdir(parents=True, exist_ok=True)

            self.used_ranges.append((offset, length))
            all_zero = True
            bytes_left = length
            cursor = offset

            with open(out_file, "wb") as dest:
                while bytes_left > 0:
                    idx = self._find_slice_index(cursor)
                    slice_start = (
                        cursor if idx == 0
                        else cursor - self.part_boundaries[idx - 1]
                    )
                    take = min(
                        bytes_left,
                        self.part_boundaries[idx] - cursor,
                        self.chunk_size,
                    )

                    self.file_handles[idx].seek(slice_start)
                    chunk = self.file_handles[idx].read(take)
                    if not chunk:
                        raise OSError("Unexpected end of data stream.")

                    if all_zero and any(chunk):
                        all_zero = False

                    dest.write(chunk)
                    bytes_left -= len(chunk)
                    cursor += len(chunk)

            if all_zero:
                out_file.unlink(missing_ok=True)
                if not is_missed:
                    self.stats.skipped_null += 1
                return False

            if not is_missed:
                self.stats.extracted += 1

            self.logger.debug(
                "Successfully saved: %s (%s bytes)",
                target_rel_path, f"{length:,}",
            )
            return True

        except SecurityError as exc:
            self.logger.error("SECURITY: %s", exc)
            self._record_failure(target_rel_path, offset, length, str(exc), is_missed)
            return False
        except Exception as exc:
            self.logger.error("Failed extracting %s: %s", target_rel_path, exc)
            if out_file and out_file.exists():
                try:
                    out_file.unlink()
                except OSError:
                    pass
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
            AuditRecord(
                path=path,
                offset=offset,
                length=length,
                reason=reason,
                is_unmapped=is_missed,
            )
        )

    # ---- progress & item iteration ---------------------------------------

    def _render_progress(self, current: int, total: int, filename: str) -> None:
        if self.debug or not Terminal.enabled() or total == 0:
            return

        bar_len = 26
        ratio = current / total
        filled = int(bar_len * ratio)
        bar = (
            f"{Terminal.GREEN}{'━' * filled}"
            f"{Terminal.DIM}{'─' * (bar_len - filled)}{Terminal.RESET}"
        )
        fn = (
            filename[:21] + ".." if len(filename) > 23 else filename.ljust(23)
        )
        sys.stdout.write(
            f"\r\x1b[K{Terminal.CYAN}⠸{Terminal.RESET} [{bar}] "
            f"{ratio * 100:5.1f}% ({current}/{total}) "
            f"{Terminal.DIM}{fn}{Terminal.RESET}"
        )
        sys.stdout.flush()

    def process_items(self) -> None:
        if self.root is None:
            return

        items = self.root.findall("BackupItem")
        self.stats.total_items = len(items)
        self.logger.info(
            "Unpacking %s catalog entries...",
            Terminal.style(str(len(items)), Terminal.BOLD),
        )

        for index, item in enumerate(items, start=1):
            category = item.get("Category", "UNKNOWN")
            display_name = category
            try:
                if category == "APPLICATION":
                    apps = item.findall("APPLICATION")
                    for app in apps:
                        name = app.get("FileName") or app.get("Name") or "unknown.apk"
                        clean_name = Path(name.replace("\\", "/")).name
                        start = int(app.get("StartOffset", 0))
                        size = int(app.get("DataSize", 0))
                        display_name = f"app/{clean_name}"
                        self.extract_stream(display_name, start, size)
                    if len(apps) > 1:
                        display_name = f"app/ [{len(apps)} packages]"
                else:
                    file_name = item.get("FileName", "")
                    dest = f"{category}-{file_name}".rstrip("-")

                    if "_CG_" in dest and self.try_path_reconstruct:
                        resolved = self.resolve_cg_path(category).lstrip("/")
                        dest = f"media/{resolved}"
                    else:
                        dest = f"records/{dest}"

                    display_name = dest
                    self.extract_stream(
                        dest,
                        int(item.get("StartOffset", 0)),
                        int(item.get("DataSize", 0)),
                    )
            except (ValueError, TypeError) as exc:
                self.logger.error(
                    "Corrupted record element skipped [%s]: %s", category, exc
                )
                self.stats.failed += 1

            self._render_progress(index, len(items), display_name)

        if not self.debug and Terminal.enabled() and items:
            sys.stdout.write("\r\x1b[K")
            sys.stdout.flush()

    # ---- orphan scanning --------------------------------------------------

    def extract_unmapped_regions(self) -> None:
        """Dump byte ranges not covered by any XML catalog entry."""
        if not self.extract_unmapped_enabled:
            self.logger.info("Orphan raw sector scan bypassed (--no-unmapped).")
            return

        self.logger.info("Analyzing archive for unmapped forensic data blocks...")
        merged: List[Tuple[int, int]] = []
        for start, length in sorted(self.used_ranges):
            end = start + length
            if not merged or start > merged[-1][1]:
                merged.append((start, end))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))

        tail_end = max(0, self.total_size - TRAILER_SIZE)
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

    # ---- summary ----------------------------------------------------------
