import struct
import xml.etree.ElementTree as ET
from hashlib import sha256
from typing import Optional
from Crypto.Cipher import AES
from .common import ENC_KEY,MAX_HEADER_SIZE,MIN_HEADER_SIZE,MIN_LOCK_CHECK_SIZE,CorruptedArchiveError,Terminal
class MetadataMixin:
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
