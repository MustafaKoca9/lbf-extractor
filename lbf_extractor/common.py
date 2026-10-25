"""Shared constants, data models, exceptions, and terminal/logging helpers."""
from __future__ import annotations

import datetime
import logging
import os
import platform
import re
import sys
from dataclasses import dataclass

__version__ = "1.3.0"
__author__ = "Mustafa Koca"
__license__ = "MIT"
__repository__ = "https://github.com/MustafaKoca9/lbf-extractor"

LOGGER_NAME = "lbf_extractor"

# The format uses this fixed passphrase as input to SHA-256 for the AES key.
ENC_KEY = b"cd562f61-5399-3978-ac76-7c54b0508010"
CHUNK_SIZE = 1024 * 1024
MAX_HEADER_SIZE = 20 * 1024 * 1024
MIN_HEADER_SIZE = 1
TRAILER_SIZE = 14
MIN_LOCK_CHECK_SIZE = 33

ANSI_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class LBFExtractorError(Exception):
    """Base class for errors raised by this package."""


class SecurityError(LBFExtractorError):
    """An archive entry resolves outside the selected output directory."""


class CorruptedArchiveError(LBFExtractorError):
    """The archive layout or its metadata is structurally invalid."""


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


class Terminal:
    """ANSI styling that stays plain in redirected output and non-TTY environments."""

    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    _initialized = False

    @classmethod
    def init(cls) -> None:
        if cls._initialized:
            return
        if platform.system() == "Windows":
            try:
                os.system("")
            except OSError:
                pass
        cls._initialized = True

    @classmethod
    def enabled(cls) -> bool:
        if os.getenv("NO_COLOR"):
            return False
        try:
            if not sys.stdout.isatty():
                return False
        except (AttributeError, OSError):
            return False
        cls.init()
        return True

    @classmethod
    def style(cls, text: str, *styles: str) -> str:
        if not styles or not cls.enabled():
            return text
        return f"{''.join(styles)}{text}{cls.RESET}"

    @classmethod
    def clean_len(cls, text: str) -> int:
        return len(ANSI_RE.sub("", text))


class ColoredFormatter(logging.Formatter):
    """Timestamped formatter that adds colors only when stdout is interactive."""

    LEVEL_MAP = {
        logging.DEBUG: (Terminal.DIM, "DBG"),
        logging.INFO: (Terminal.CYAN, "INF"),
        logging.WARNING: (Terminal.YELLOW, "WRN"),
        logging.ERROR: (Terminal.RED, "ERR"),
        logging.CRITICAL: (Terminal.RED + Terminal.BOLD, "CRT"),
    }

    def format(self, record: logging.LogRecord) -> str:
        color, tag = self.LEVEL_MAP.get(record.levelno, ("", record.levelname[:3]))
        timestamp = datetime.datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        time_label = Terminal.style(f"[{timestamp}]", Terminal.DIM)
        level_label = Terminal.style(tag, color) if color else tag
        return f"{time_label} [{level_label}] {record.getMessage()}"
