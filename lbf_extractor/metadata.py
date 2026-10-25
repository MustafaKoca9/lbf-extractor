"""Header parsing, decryption, password-flag inspection, and metadata helpers."""
from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
from hashlib import sha256

from Crypto.Cipher import AES

from .common import (
    ENC_KEY,
    MAX_HEADER_SIZE,
    MIN_HEADER_SIZE,
    MIN_LOCK_CHECK_SIZE,
    CorruptedArchiveError,
    Terminal,
)


class MetadataMixin:
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

    def decrypt_payload(self, cipher_data: bytes) -> bytes:
        if not cipher_data or len(cipher_data) % AES.block_size:
            raise CorruptedArchiveError(
                f"Encrypted payload must be aligned to {AES.block_size} bytes "
                f"(received {len(cipher_data)})."
            )
        cipher = AES.new(sha256(ENC_KEY).digest(), AES.MODE_ECB)
        return self.strip_pkcs7(cipher.decrypt(cipher_data))

    def get_header_length(self, is_new: bool) -> int:
        position = 1 if is_new else self.total_size - 5
        length = struct.unpack("!L", self.read_bytes(position, 4))[0]
        if not MIN_HEADER_SIZE <= length <= MAX_HEADER_SIZE:
            raise CorruptedArchiveError(f"Header size is outside allowed bounds: {length:,} bytes")
        return length

    def parse_header(self, is_new: bool) -> ET.Element:
        label = "NEW" if is_new else "OLD"
        self.logger.info(
            "Evaluating header format: [%s]",
            Terminal.style(label, Terminal.BOLD),
        )

        pointer = 5 if is_new else self.total_size - 13
        header_start = struct.unpack("!Q", self.read_bytes(pointer, 8))[0]
        header_size = self.get_header_length(is_new)

        if header_start > self.total_size or header_size > self.total_size - header_start:
            raise CorruptedArchiveError(
                "Header XML range extends past the end of the archive."
            )

        encrypted = self.read_bytes(header_start, header_size)
        decrypted = self.decrypt_payload(encrypted)
        text = decrypted.decode("utf-8", errors="ignore").strip("\\x00 \\r\\n\\t")

        xml_start = text.find("<?xml")
        if xml_start < 0:
            xml_start = text.find("<")
        if xml_start < 0:
            raise CorruptedArchiveError("Decrypted header contains no recognizable XML.")

        clean_xml = text[xml_start:]
        # Parse before writing: an unsuccessful format guess must not leave a
        # misleading header file behind or truncate an existing one.
        root = ET.fromstring(clean_xml)
        dump_target = self.get_safe_destination(f"header-{label.lower()}.xml")
        dump_target.write_text(clean_xml, encoding="utf-8")

        self.header_format = "new" if is_new else "old"
        return root

    def resolve_cg_path(self, category: str) -> str:
        """Resolve an LG *_CG_<index> reference through the Common metadata."""
        parts = category.split("_CG_", 1)
        if len(parts) != 2 or self.common_header is None:
            return category

        try:
            job, index_text = parts
            index = int(index_text)
        except (TypeError, ValueError):
            return category

        target_name = f"KEY_MEDIA_JOB_{job}KEY_MEDIA_TYPE_0"
        for element in self.common_header.findall("Attr"):
            if element.get("Name") != target_name or not element.text:
                continue
            tokens = element.text.split("@@")
            if 0 <= index < len(tokens):
                return tokens[index].replace("@", "")

        self.logger.debug("No Common metadata value found for CG token %r", category)
        return category

    def check_lock_status(self) -> None:
        """Inspect the archive trailer for the password flag and stored SHA-1."""
        if self.total_size < MIN_LOCK_CHECK_SIZE:
            raise CorruptedArchiveError(
                f"Archive is too small ({self.total_size} bytes; "
                f"minimum {MIN_LOCK_CHECK_SIZE})."
            )

        is_locked = self.read_bytes(self.total_size - 1, 1) != b"\\x00"
        if is_locked:
            password_sha1 = self.read_bytes(self.total_size - 33, 20).hex()
            self.logger.warning(
                "Archive is marked as %s. Stored password SHA-1: %s",
                Terminal.style("PASSWORD ENCRYPTED", Terminal.RED, Terminal.BOLD),
                Terminal.style(password_sha1, Terminal.YELLOW),
            )
        else:
            self.logger.info("Security check: archive is marked as unlocked.")
