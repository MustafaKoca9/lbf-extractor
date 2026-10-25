"""Header decoding and metadata parsing built on ArchiveReader and OutputManager."""
from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
from hashlib import sha256
from typing import Optional

from Crypto.Cipher import AES

from .archive import ArchiveReader
from .common import (
    ENC_KEY,
    MAX_HEADER_SIZE,
    MIN_HEADER_SIZE,
    MIN_LOCK_CHECK_SIZE,
    CorruptedArchiveError,
    Terminal,
)
from .paths import OutputManager


class MetadataParser:
    """Parse and interpret header metadata without owning archive file handles."""

    def __init__(self, archive: ArchiveReader, output: OutputManager, logger) -> None:
        self.archive = archive
        self.output = output
        self.logger = logger
        self.header_format: Optional[str] = None

    @staticmethod
    def strip_pkcs7(payload: bytes) -> bytes:
        if not payload:
            return payload
        padding = payload[-1]
        if (
            1 <= padding <= AES.block_size
            and len(payload) >= padding
            and payload[-padding:] == bytes([padding]) * padding
        ):
            return payload[:-padding]
        return payload

    @staticmethod
    def decrypt_payload(cipher_data: bytes) -> bytes:
        if not cipher_data or len(cipher_data) % AES.block_size:
            raise CorruptedArchiveError(
                f"Encrypted payload must be aligned to {AES.block_size} bytes "
                f"(received {len(cipher_data)})."
            )
        cipher = AES.new(sha256(ENC_KEY).digest(), AES.MODE_ECB)
        return MetadataParser.strip_pkcs7(cipher.decrypt(cipher_data))

    def get_header_length(self, is_new: bool) -> int:
        position = 1 if is_new else self.archive.total_size - 5
        length = struct.unpack("!L", self.archive.read_bytes(position, 4))[0]
        if not MIN_HEADER_SIZE <= length <= MAX_HEADER_SIZE:
            raise CorruptedArchiveError(
                f"Header size is outside allowed bounds: {length:,} bytes"
            )
        return length

    def parse_header(self, is_new: bool) -> ET.Element:
        label = "NEW" if is_new else "OLD"
        self.logger.info(
            "Evaluating header format: [%s]",
            Terminal.style(label, Terminal.BOLD),
        )

        pointer = 5 if is_new else self.archive.total_size - 13
        header_start = struct.unpack("!Q", self.archive.read_bytes(pointer, 8))[0]
        header_size = self.get_header_length(is_new)

        if (
            header_start > self.archive.total_size
            or header_size > self.archive.total_size - header_start
        ):
            raise CorruptedArchiveError(
                "Header XML range extends past the end of the archive."
            )

        encrypted = self.archive.read_bytes(header_start, header_size)
        decrypted = self.decrypt_payload(encrypted)
        text = decrypted.decode("utf-8", errors="ignore").strip("\x00 \r\n\t")

        xml_start = text.find("<?xml")
        if xml_start < 0:
            xml_start = text.find("<")
        if xml_start < 0:
            raise CorruptedArchiveError("Decrypted header contains no recognizable XML.")

        clean_xml = text[xml_start:]
        root = ET.fromstring(clean_xml)
        self.output.write_text(f"header-{label.lower()}.xml", clean_xml)
        self.header_format = "new" if is_new else "old"
        return root

    def resolve_cg_path(
        self,
        category: str,
        common_header: Optional[ET.Element],
    ) -> str:
        """Resolve an LG *_CG_<index> reference through a supplied Common node."""
        parts = category.split("_CG_", 1)
        if len(parts) != 2 or common_header is None:
            return category

        job, index_text = parts
        try:
            index = int(index_text)
        except ValueError:
            return category

        target_name = f"KEY_MEDIA_JOB_{job}KEY_MEDIA_TYPE_0"
        for element in common_header.findall("Attr"):
            if element.get("Name") != target_name or not element.text:
                continue
            tokens = element.text.split("@@")
            if 0 <= index < len(tokens):
                return tokens[index].replace("@", "")

        self.logger.debug("No Common metadata value found for CG token %r", category)
        return category

    def check_lock_status(self) -> bool:
        """Inspect the archive trailer and return whether it is marked locked."""
        if self.archive.total_size < MIN_LOCK_CHECK_SIZE:
            raise CorruptedArchiveError(
                f"Archive is too small ({self.archive.total_size} bytes; "
                f"minimum {MIN_LOCK_CHECK_SIZE})."
            )

        is_locked = self.archive.read_bytes(self.archive.total_size - 1, 1) != b"\x00"
        if is_locked:
            password_sha1 = self.archive.read_bytes(
                self.archive.total_size - 33, 20
            ).hex()
            self.logger.warning(
                "Archive is marked as %s. Stored password SHA-1: %s",
                Terminal.style("PASSWORD ENCRYPTED", Terminal.RED, Terminal.BOLD),
                Terminal.style(password_sha1, Terminal.YELLOW),
            )
        else:
            self.logger.info("Security check: archive is marked as unlocked.")
        return is_locked
