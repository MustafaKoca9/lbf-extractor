#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
lbf-extractor — LG Mobile Switch (.lbf) Backup Inspector & Forensic Extractor.

Features:
- High-performance chunk-based logical streaming across split backup files.
- Dual header engine (Legacy format trailer vs. Modern header architecture).
- AES-128-ECB decryption with SHA-256-derived key and PKCS#7 unpadding.
- Zip-Slip / Path Traversal mitigation with canonical path confinement
  (token filter + realpath/commonpath).
- Orphan/unmapped raw block recovery for digital forensics.
- ANSI terminal UI (progress indicator, colored logs, aligned audit table)
  with zero heavyweight dependencies.

Split-archive note:
    LG Mobile Switch typically stores multipart backups as
    ``.lbf0``, ``.lbf1``, …, ``.lbf`` (primary last). If your backup
    uses the opposite convention (primary first), pass
    ``--split-lbf-first``. Use ``--debug`` to print the exact
    assembly order.

Dependencies:
    pycryptodome  (pip install pycryptodome)

Usage:
    python lbf_extractor.py backup.lbf -o ./recovered
    python lbf_extractor.py backup.lbf --overwrite --debug
    python lbf_extractor.py backup.lbf --split-lbf-first

Author : Mustafa Koca
License: MIT
"""

from __future__ import annotations

import argparse
import datetime
import io
import logging
import os
import platform
import re
import struct
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional, Tuple

# -----------------------------------------------------------------------------
# Dependency validation
# -----------------------------------------------------------------------------
try:
    from Crypto.Cipher import AES
except ImportError:
    sys.stderr.write(
        "\n\033[91m[!] Missing Dependency:\033[0m pycryptodome is required.\n"
        "    Install it via: \033[96mpip install pycryptodome\033[0m\n\n"
    )
    sys.exit(1)


# -----------------------------------------------------------------------------
# Metadata & constants
# -----------------------------------------------------------------------------
__version__ = "1.2.1"
__author__ = "Mustafa Koca"
__license__ = "MIT"
__repository__ = "https://github.com/mustafakoca/lbf-extractor"

LOGGER_NAME = "lbf_extractor"

# LG Mobile Switch AES passphrase (fixed constant in the file format)
ENC_KEY: bytes = b"cd562f61-5399-3978-ac76-7c54b0508010"

CHUNK_SIZE: int = 1024 * 1024            # 1 MiB streaming buffer
MAX_HEADER_SIZE: int = 20 * 1024 * 1024  # 20 MiB sanity boundary
MIN_HEADER_SIZE: int = 1
TRAILER_SIZE: int = 14                   # trailer bytes excluded from orphan scan
MIN_LOCK_CHECK_SIZE: int = 33            # 20 (SHA-1) + 12 + 1 flag byte

ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

_INSTANCE_COUNTER = 0


# -----------------------------------------------------------------------------
# Custom exceptions
# -----------------------------------------------------------------------------
class LBFExtractorError(Exception):
    """Base exception for all extractor errors."""


class SecurityError(LBFExtractorError):
    """Raised when an archive entry attempts directory traversal."""


class CorruptedArchiveError(LBFExtractorError):
    """Raised when archive header or structural boundaries are invalid."""


# -----------------------------------------------------------------------------
# Terminal styling
# -----------------------------------------------------------------------------
class Terminal:
    """ANSI terminal styling with cross-platform, idempotent fallback."""

    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    _initialized: bool = False

    @classmethod
    def init(cls) -> None:
        """Enable VT100 processing on Windows (idempotent, safe everywhere)."""
        if cls._initialized:
            return
        if platform.system() == "Windows":
            try:
                os.system("")
            except Exception:
                pass
        cls._initialized = True

    @classmethod
    def enabled(cls) -> bool:
        """True if ANSI escapes will actually be interpreted by the terminal."""
        if os.getenv("NO_COLOR"):
            return False
        try:
            if not sys.stdout.isatty():
                return False
        except Exception:
            return False
        cls.init()
        return True

    @classmethod
    def style(cls, text: str, *styles: str) -> str:
        """Wrap text with the given style codes when the terminal supports it."""
        if not styles or not cls.enabled():
            return text
        return f"{''.join(styles)}{text}{cls.RESET}"

    @classmethod
    def clean_len(cls, styled_text: str) -> int:
        """Visible character length of an ANSI-styled string."""
        return len(ANSI_RE.sub("", styled_text))


# -----------------------------------------------------------------------------
# Dataclasses
# -----------------------------------------------------------------------------
@dataclass
class ExtractionStats:
    total_items: int = 0
    extracted: int = 0
    skipped_null: int = 0
    failed: int = 0
    missed_blocks: int = 0
    missed_failed: int = 0


@dataclass
class AuditRecord:
    path: str
    offset: int
    length: int
    reason: str
    is_unmapped: bool = False


# -----------------------------------------------------------------------------
# Logging formatter
# -----------------------------------------------------------------------------
class ColoredFormatter(logging.Formatter):
    """Level-colored, timestamped log formatter."""

    LEVEL_MAP = {
        logging.DEBUG: (Terminal.DIM, "DBG"),
        logging.INFO: (Terminal.CYAN, "INF"),
        logging.WARNING: (Terminal.YELLOW, "WRN"),
        logging.ERROR: (Terminal.RED, "ERR"),
        logging.CRITICAL: (Terminal.RED + Terminal.BOLD, "CRT"),
    }

    def format(self, record: logging.LogRecord) -> str:
        color, tag = self.LEVEL_MAP.get(record.levelno, ("", record.levelname[:3]))
        ts = datetime.datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        prefix = f"{Terminal.DIM}[{ts}]{Terminal.RESET} [{Terminal.style(tag, color)}] "
        return f"{prefix}{record.getMessage()}"


# -----------------------------------------------------------------------------
# Main extractor
# -----------------------------------------------------------------------------
class LBFExtractor:
    """Streaming unpacker and parser for segmented LG .lbf archives."""

    def __init__(
        self,
        file_path: str,
        output_dir: str = "./export",
        try_path_reconstruct: bool = True,
        force_new_header: bool = False,
        force_old_header: bool = False,
        split_lbf_first: bool = False,
        overwrite: bool = False,
        extract_unmapped: bool = True,
        debug: bool = False,
        log_file: Optional[str] = None,
    ) -> None:
        if not file_path.lower().endswith(".lbf"):
            raise ValueError(f"Target must be a valid .lbf archive: {file_path}")
        if force_new_header and force_old_header:
            raise ValueError(
                "Parameters --force-new and --force-old are mutually exclusive."
            )

        global _INSTANCE_COUNTER
        _INSTANCE_COUNTER += 1
        self._instance_seq = _INSTANCE_COUNTER

        self.archive_path = Path(file_path).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.try_path_reconstruct = try_path_reconstruct
        self.force_new_header = force_new_header
        self.force_old_header = force_old_header
        self.split_lbf_first = split_lbf_first
        self.overwrite = overwrite
        self.extract_unmapped_enabled = extract_unmapped
        self.debug = debug

        # Streaming state
        self.part_paths: List[Path] = []
        self.file_handles: List[BinaryIO] = []
        self.part_boundaries: List[int] = []
        self.total_size: int = 0
        self.used_ranges: List[Tuple[int, int]] = []

        # XML metadata
        self.root: Optional[ET.Element] = None
        self.common_header: Optional[ET.Element] = None
        self.header_format: Optional[str] = None  # "new" | "old"

        # Stats & audit
        self.stats = ExtractionStats()
        self.audit_failed: List[AuditRecord] = []
        self.audit_missed: List[Dict[str, int]] = []
        self.start_time: Optional[datetime.datetime] = None
        self.end_time: Optional[datetime.datetime] = None

        self.logger = self._init_logger(debug, log_file)

    # ---- logging ----------------------------------------------------------
    def _init_logger(self, debug: bool, log_file: Optional[str]) -> logging.Logger:
        # Per-instance logger name prevents accidental handler clobbering
        # when multiple extractors coexist (e.g. in a library context).
        logger = logging.getLogger(f"{LOGGER_NAME}.{self._instance_seq}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        logger.handlers.clear()

        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.DEBUG if debug else logging.INFO)
        console.setFormatter(ColoredFormatter())
        logger.addHandler(console)

        if log_file:
            fh = logging.FileHandler(log_file, mode="w", encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)-8s] "
                    "<%(filename)s:%(lineno)d> %(message)s"
                )
            )
            logger.addHandler(fh)

        return logger

    # ---- context manager --------------------------------------------------
    def __enter__(self) -> "LBFExtractor":
        Terminal.init()
        self.start_time = datetime.datetime.now()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if any(self.output_dir.iterdir()):
            self.logger.warning(
                "Export destination is not empty. Existing files will be "
                "versioned to avoid collisions."
            )

        try:
            self._load_archive_segments()
        except Exception:
            self._cleanup()
            raise

        self._print_banner()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._cleanup()
        self.end_time = datetime.datetime.now()

    def _cleanup(self) -> None:
        """Close file handles and detach the logger's handlers (idempotent)."""
        for fh in self.file_handles:
            try:
                fh.close()
            except OSError:
                pass
        self.file_handles.clear()

        for h in self.logger.handlers[:]:
            try:
                h.close()
            except Exception:
                pass
            self.logger.removeHandler(h)

    # ---- banners / segment discovery -------------------------------------
    def _print_banner(self) -> None:
        print(
            f"{Terminal.CYAN}{Terminal.BOLD}LG Backup Extractor (lbf-extractor){Terminal.RESET} "
            f"v{__version__} by {__author__}\n"
            f"Archive: {Terminal.style(self.archive_path.name, Terminal.BOLD)} "
            f"({self.total_size / (1024 * 1024):,.2f} MiB across "
            f"{len(self.part_paths)} part(s))\n"
            f"{Terminal.DIM}Platform: {platform.system()} {platform.release()} | "
            f"Python: {platform.python_version()}{Terminal.RESET}\n"
        )
        if len(self.part_paths) > 1:
            self.logger.info("Multipart slice assembly order:")
            for idx, p in enumerate(self.part_paths):
                self.logger.info(
                    "  [%d] %s (%s bytes)", idx, p.name, f"{p.stat().st_size:,}"
                )

    def _load_archive_segments(self) -> None:
        """Discover and open .lbf plus .lbf0/.lbf1/… slices in logical order.

        Default order (LG convention): .lbf0, .lbf1, …, .lbf (primary last).
        Pass ``split_lbf_first=True`` for the opposite convention.
        """
        slices: List[Path] = []
        idx = 0
        while True:
            sliced = self.archive_path.parent / f"{self.archive_path.name}{idx}"
            if sliced.is_file():
                slices.append(sliced)
                idx += 1
            else:
                break

        paths = (
            [self.archive_path] + slices
            if self.split_lbf_first
            else slices + [self.archive_path]
        )

        cumulative = 0
        try:
            for path in paths:
                fh = open(path, "rb")
                fh.seek(0, os.SEEK_END)
                cumulative += fh.tell()
                self.file_handles.append(fh)
                self.part_boundaries.append(cumulative)
        except OSError:
            self._cleanup()
            raise

        self.part_paths = paths
        self.total_size = cumulative

    # ---- logical reads ----------------------------------------------------
    def _find_slice_index(self, offset: int) -> int:
        if offset < 0 or offset >= self.total_size:
            raise IndexError(
                f"Logical offset out of boundary: {offset:,} / {self.total_size:,}"
            )
        for i, boundary in enumerate(self.part_boundaries):
            if offset < boundary:
                return i
        raise RuntimeError(f"Unresolvable slice index for offset {offset}")

    def read_bytes(self, offset: int, length: int) -> bytes:
        """Read a byte buffer spanning any number of segment boundaries."""
        if length < 0 or offset < 0 or offset + length > self.total_size:
            raise ValueError(
                f"Illegal boundary read requested: "
                f"offset={offset:,}, length={length:,}"
            )

        buf = io.BytesIO()
        remaining = length
        cursor = offset
        while remaining > 0:
            idx = self._find_slice_index(cursor)
            slice_start = (
                cursor if idx == 0 else cursor - self.part_boundaries[idx - 1]
            )
            available = self.part_boundaries[idx] - cursor
            take = min(remaining, available)

            self.file_handles[idx].seek(slice_start)
            data = self.file_handles[idx].read(take)
            if len(data) != take:
                raise OSError("Unexpected early EOF while reading segment slice.")

            buf.write(data)
            cursor += take
            remaining -= take

        self.used_ranges.append((offset, length))
        return buf.getvalue()

    # ---- destination path safety -----------------------------------------
    def get_safe_destination(self, virtual_path: str) -> Path:
        """Sanitize, confine to output_dir, then de-duplicate.

        Raises:
            SecurityError: if a canonical path check escapes the output root.
        """
        sanitized = virtual_path.replace("\\", "/").strip("/")
        tokens = [t for t in sanitized.split("/") if t not in ("", ".")]

        if any(t == ".." for t in tokens):
            self.logger.warning(
                "Path traversal sequence '..' blocked in: %r", virtual_path
            )
            tokens = [t for t in tokens if t != ".."]

        if not tokens:
            tokens = ["unnamed_item"]

        candidate = (self.output_dir / Path(*tokens)).resolve()

        try:
            common = os.path.commonpath(
                [str(self.output_dir), str(candidate)]
            )
        except ValueError as exc:
            raise SecurityError(
                f"Cross-drive path traversal blocked: {virtual_path!r} ({exc})"
            ) from exc

        if common != str(self.output_dir):
            raise SecurityError(
                f"Directory traversal exploit detected: {virtual_path!r} "
                f"resolves to {candidate}"
            )

        if not self.overwrite and candidate.exists():
            original = candidate
            stem, suffix = original.stem, original.suffix
            counter = 1
            while candidate.exists():
                candidate = original.with_name(f"{stem}_{counter}{suffix}")
                counter += 1

        return candidate

    # ---- crypto / header --------------------------------------------------
    @staticmethod
    def strip_pkcs7(payload: bytes) -> bytes:
        if not payload:
            return payload
        pad = payload[-1]
        if 1 <= pad <= 16 and len(payload) >= pad and payload[-pad:] == bytes([pad]) * pad:
            return payload[:-pad]
        return payload

    def decrypt_payload(self, cipher_data: bytes) -> bytes:
        if not cipher_data or len(cipher_data) % AES.block_size != 0:
            raise CorruptedArchiveError(
                f"Encrypted payload must align to 16 bytes (got {len(cipher_data)})."
            )
        cipher = AES.new(sha256(ENC_KEY).digest(), AES.MODE_ECB)
        return self.strip_pkcs7(cipher.decrypt(cipher_data))

    def get_header_length(self, is_new: bool) -> int:
        pos = 1 if is_new else self.total_size - 5
        length = struct.unpack("!L", self.read_bytes(pos, 4))[0]
        if not MIN_HEADER_SIZE <= length <= MAX_HEADER_SIZE:
            raise CorruptedArchiveError(
                f"Header size constraint violation: {length:,} bytes"
            )
        return length

    def parse_header(self, is_new: bool) -> ET.Element:
        tag = "NEW" if is_new else "OLD"
        self.logger.info(
            "Evaluating header architecture format: [%s]",
            Terminal.style(tag, Terminal.BOLD),
        )

        ptr = 5 if is_new else self.total_size - 13
        header_start = struct.unpack("!Q", self.read_bytes(ptr, 8))[0]
        header_size = self.get_header_length(is_new)

        if header_start + header_size > self.total_size:
            raise CorruptedArchiveError(
                "Header XML descriptor spans beyond total archive boundary."
            )

        decrypted = self.decrypt_payload(self.read_bytes(header_start, header_size))
        text = decrypted.decode("utf-8", errors="ignore").strip("\x00 \r\n\t")

        xml_start = text.find("<?xml")
        if xml_start < 0:
            xml_start = text.find("<")
        if xml_start < 0:
            raise CorruptedArchiveError(
                "Decrypted stream does not contain recognizable XML."
            )

        clean_xml = text[xml_start:]
        dump_target = self.get_safe_destination(f"header-{tag.lower()}.xml")
        dump_target.write_text(clean_xml, encoding="utf-8")

        root = ET.fromstring(clean_xml)  # may raise ET.ParseError; caller retries
        self.header_format = "new" if is_new else "old"
        return root

    # ---- metadata helpers -------------------------------------------------
    def resolve_cg_path(self, category: str) -> str:
        """Resolve LG ``*_CG_<idx>`` path references via Common header metadata."""
        try:
            parts = category.split("_CG_")
            if len(parts) < 2 or self.common_header is None:
                return category
            job, index = parts[0], int(parts[1])
            target_attr = f"KEY_MEDIA_JOB_{job}KEY_MEDIA_TYPE_0"
            for el in self.common_header.findall("Attr"):
                if el.get("Name") == target_attr and el.text:
                    tokens = el.text.split("@@")
                    if 0 <= index < len(tokens):
                        return tokens[index].replace("@", "")
        except Exception as err:
            self.logger.debug("Failed resolving CG token (%s): %s", category, err)
        return category

    def check_lock_status(self) -> None:
        """Inspect the archive trailer for password flag and hash."""
        if self.total_size < MIN_LOCK_CHECK_SIZE:
            raise CorruptedArchiveError(
                f"File size ({self.total_size} bytes) is too small to be a "
                f"valid LG backup archive (need ≥ {MIN_LOCK_CHECK_SIZE})."
            )

        is_locked = self.read_bytes(self.total_size - 1, 1) != b"\x00"
        if is_locked:
            pw_sha1 = self.read_bytes(self.total_size - 33, 20).hex()
            self.logger.warning(
                "Archive is marked as %s! Password SHA-1: %s",
                Terminal.style("PASSWORD ENCRYPTED", Terminal.RED, Terminal.BOLD),
                Terminal.style(pw_sha1, Terminal.YELLOW),
            )
        else:
            self.logger.info("Security check: archive is unencrypted/unlocked.")

    # ---- streaming extraction --------------------------------------------
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
                        CHUNK_SIZE,
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
    @staticmethod
    def _format_row(label: str, raw_value: str, *styles: str) -> str:
        """Format a two-cell report row with guaranteed alignment.

        Left cell : 38 visible chars  (│ + left + │)
        Right cell: 19 visible chars  (│ + right + │)
        """
        if len(label) > 35:
            label = label[:33] + ".."
        left = f"  {label:<35} "

        if len(raw_value) > 15:
            raw_value = raw_value[:13] + ".."
        styled = Terminal.style(raw_value, *styles) if styles else raw_value
        pad = 17 - len(raw_value)
        right = f" {styled}{' ' * pad} "

        border = Terminal.style("│", Terminal.CYAN)
        return f"{border}{left}{border}{right}{border}"

    def print_summary_box(self) -> None:
        """Render an aligned Unicode audit box to stdout."""
        elapsed = (
            (self.end_time - self.start_time).total_seconds()
            if self.start_time and self.end_time
            else 0.0
        )

        print("\n" + Terminal.style("┌" + "─" * 58 + "┐", Terminal.CYAN))

        header_text = "EXTRACTION AUDIT REPORT"
        header_left = (58 - len(header_text)) // 2
        header_right = 58 - len(header_text) - header_left
        header = (
            f"{Terminal.BOLD}{' ' * header_left}{header_text}"
            f"{' ' * header_right}{Terminal.RESET}"
        )
        print(Terminal.style("│", Terminal.CYAN) + header + Terminal.style("│", Terminal.CYAN))
        print(Terminal.style("├" + "─" * 38 + "┬" + "─" * 19 + "┤", Terminal.CYAN))

        rows = [
            ("Catalog Items Located", str(self.stats.total_items), ()),
            ("Files Extracted Successfully", str(self.stats.extracted),
             (Terminal.GREEN, Terminal.BOLD)),
            ("Unmapped Forensic Blocks", str(self.stats.missed_blocks), ()),
            ("Skipped (Sparse / Null Content)", str(self.stats.skipped_null), ()),
            ("Failed Catalog Operations", str(self.stats.failed),
             (Terminal.RED,) if self.stats.failed else (Terminal.DIM,)),
            ("Failed Unmapped Blocks", str(self.stats.missed_failed),
             (Terminal.YELLOW,) if self.stats.missed_failed else (Terminal.DIM,)),
            ("Execution Duration", f"{elapsed:.2f}s", ()),
        ]
        for label, value, styles in rows:
            print(self._format_row(label, value, *styles))

        print(Terminal.style("└" + "─" * 38 + "┴" + "─" * 19 + "┘", Terminal.CYAN))

        if self.audit_failed:
            print(
                f"\n{Terminal.style('Failure Audit Records:', Terminal.RED, Terminal.BOLD)}"
            )
            for item in self.audit_failed:
                tag = "[UNMAPPED]" if item.is_unmapped else "[CATALOG] "
                print(
                    f"  • {tag} {item.path} "
                    f"[offset: {item.offset:,}, len: {item.length:,}]: {item.reason}"
                )

    # ---- pipeline ---------------------------------------------------------
    def execute(self) -> None:
        """Run the complete extraction pipeline."""
        self.check_lock_status()

        preferred_new = (
            True if self.force_new_header
            else False if self.force_old_header
            else True
        )

        try:
            self.root = self.parse_header(preferred_new)
        except Exception as primary_err:
            self.logger.warning(
                "Primary header parse failed (%s); trying alternate scheme...",
                primary_err,
            )
            self.root = self.parse_header(not preferred_new)

        self.common_header = self.root.find("Common")
        if self.common_header is None:
            raise CorruptedArchiveError(
                "Corrupted XML metadata: <Common> descriptor missing from header root."
            )

        is_new_el = self.common_header.find("IsNew")
        if (
            not self.force_new_header
            and not self.force_old_header
            and self.header_format != "new"
            and is_new_el is not None
            and is_new_el.text == "True"
        ):
            try:
                new_root = self.parse_header(True)
                new_common = new_root.find("Common")
                if new_common is not None:
                    self.root, self.common_header = new_root, new_common
            except Exception as err:
                self.logger.debug(
                    "Automated header realignment bypassed: %s", err
                )

        # Mark byte 0 as consumed for the modern format so the orphan
        # scanner does not emit a spurious 1-byte "block_0x00000000".
        if self.header_format == "new":
            self.used_ranges.append((0, 1))

        self.process_items()
        self.extract_unmapped_regions()
        self.end_time = datetime.datetime.now()
        self.print_summary_box()
        self.logger.info("Extraction completed successfully.")


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------
def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lbf-extractor",
        description=f"LG Backup (.lbf) Forensic Extractor v{__version__}",
        epilog=(
            "Examples:\n"
            "  python lbf_extractor.py my_backup.lbf -o ./recovered\n"
            "  python lbf_extractor.py split_backup.lbf --overwrite --debug\n"
            "  python lbf_extractor.py backup.lbf --split-lbf-first\n"
            "  python lbf_extractor.py backup.lbf --force-new --no-unmapped\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("file", help="Path to the .lbf file (or primary slice)")
    parser.add_argument(
        "-o", "--output", default="./export",
        help="Output export destination directory",
    )
    parser.add_argument(
        "--no-path-reconstruct", action="store_true",
        help="Disable CG media path reconstruction",
    )
    parser.add_argument(
        "--force-new", action="store_true",
        help="Force parsing as new header format",
    )
    parser.add_argument(
        "--force-old", action="store_true",
        help="Force parsing as old header format",
    )
    parser.add_argument(
        "--split-lbf-first", action="store_true",
        help="Assemble .lbf first, followed by .lbf0, .lbf1... "
             "(default: .lbf is the last segment)",
    )
    parser.add_argument(
        "--no-unmapped", action="store_true",
        help="Bypass unmapped raw sector forensic dumping",
    )
    parser.add_argument(
        "--overwrite", action="store_true",
        help="Overwrite existing files in destination directory",
    )
    parser.add_argument(
        "--debug", action="store_true",
        help="Enable verbose debug logging",
    )
    parser.add_argument(
        "--log", metavar="FILE",
        help="Mirror logging stream to designated file",
    )
    parser.add_argument(
        "-v", "--version", action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main() -> int:
    Terminal.init()
    args = build_cli_parser().parse_args()

    # Bootstrap logger for errors before/outside the extractor context.
    boot_logger = logging.getLogger(f"{LOGGER_NAME}.main")
    boot_logger.setLevel(logging.DEBUG)
    if not boot_logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setLevel(logging.DEBUG if args.debug else logging.INFO)
        h.setFormatter(ColoredFormatter())
        boot_logger.addHandler(h)

    try:
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
        ) as extractor:
            extractor.execute()
        return 0

    except KeyboardInterrupt:
        print(f"\n{Terminal.style('[!] Aborted by user interrupt.', Terminal.YELLOW)}")
        return 130
    except Exception as exc:
        boot_logger.critical("Fatal termination: %s", exc)
        if args.debug:
            import traceback
            traceback.print_exc()
        else:
            print(
                f"{Terminal.DIM}Hint: run with --debug to show the full stack trace."
                f"{Terminal.RESET}",
                file=sys.stderr,
            )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
