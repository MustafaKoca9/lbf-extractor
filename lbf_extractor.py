#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lbf-extractor — LG Mobile Switch .lbf backup inspection and extraction.

This implementation provides a conservative, streaming extractor for personal
LG Mobile Switch backups. Validate results against backups you own.
"""
import argparse
import datetime
import logging
import os
import platform
import struct
import sys
import xml.etree.ElementTree as ET
from hashlib import sha256
from typing import Dict, List, Optional, Tuple

try:
    from Crypto.Cipher import AES
except ImportError:
    print("ERROR: pycryptodome is required. Install with: python -m pip install pycryptodome", file=sys.stderr)
    raise SystemExit(1)

__version__ = "1.0.0"
__author__ = "Mustafa Koca"
__license__ = "MIT"

# LG formatında kullanılan sabit anahtar; yalnızca kendi yedeklerinizi kurtarmak için kullanın.
ENC_KEY = b"cd562f61-5399-3978-ac76-7c54b0508010"
MAX_HEADER_SIZE = 20_971_520
MIN_HEADER_SIZE = 1
TRAILER_SIZE = 14
CHUNK_SIZE = 1024 * 1024
LOG_FORMAT = "%(asctime)s [%(levelname)-8s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class LBFExtractor:
    """LG .lbf yedek dosyasını ayrıştırır ve içeriğini çıkarır."""

    def __init__(self, file_path: str, output_dir: str = "./export",
                 try_path_reconstruct: bool = True, force_new_header: bool = False,
                 force_old_header: bool = False, overwrite: bool = False,
                 extract_unmapped: bool = True, debug: bool = False,
                 log_file: Optional[str] = None):
        if not file_path.lower().endswith(".lbf"):
            raise ValueError(f".lbf dosyası bekleniyordu: {file_path}")
        if force_new_header and force_old_header:
            raise ValueError("--force-new ve --force-old birlikte kullanılamaz")
        self.file_path = os.path.abspath(file_path)
        self.output_dir = os.path.abspath(output_dir)
        self.try_path_reconstruct = try_path_reconstruct
        self.force_new_header = force_new_header
        self.force_old_header = force_old_header
        self.overwrite = overwrite
        self.extract_unmapped_enabled = extract_unmapped
        self.data_names: List[str] = []
        self.data_files = []
        self.data_sizes: List[int] = []  # Her parçanın birleşik bitiş offset'i
        self.total_size = 0
        self.used_ranges: List[Tuple[int, int]] = []
        self.root: Optional[ET.Element] = None
        self.common_header: Optional[ET.Element] = None
        self.stats: Dict[str, int] = {
            "total_items": 0, "extracted": 0, "skipped_null": 0,
            "failed": 0, "missed_blocks": 0,
        }
        self.audit_failed: List[Dict] = []
        self.audit_missed: List[Dict] = []
        self.start_time = None
        self.end_time = None
        self.logger = self._setup_logging(debug, log_file)

    def _setup_logging(self, debug: bool, log_file: Optional[str]) -> logging.Logger:
        logger = logging.getLogger(f"LBFExtractor.{id(self)}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.DEBUG if debug else logging.INFO)
        console.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
        logger.addHandler(console)
        if log_file:
            handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
            handler.setLevel(logging.DEBUG)
            handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)-8s] <%(filename)s:%(lineno)d> %(message)s",
                LOG_DATE_FORMAT))
            logger.addHandler(handler)
        return logger

    def __enter__(self):
        self.start_time = datetime.datetime.now()
        os.makedirs(self.output_dir, exist_ok=True)
        if os.listdir(self.output_dir):
            self.logger.warning("Çıktı dizini boş değil; dosyalar yeniden adlandırılabilir.")
        self._load_parts()
        self.logger.info("LG Backup Extractor v%s — %s", __version__, __author__)
        self.logger.debug("OS: %s %s (%s) | Python: %s",
                          platform.system(), platform.release(), platform.machine(),
                          platform.python_version())
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for f in self.data_files:
            try:
                f.close()
            except Exception:
                pass
        self.end_time = datetime.datetime.now()
        if self.start_time:
            self.logger.debug("Toplam süre: %.2f saniye",
                              (self.end_time - self.start_time).total_seconds())
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)

    def _load_parts(self):
        # .lbf ana dosyası ile ardışık .lbf0, .lbf1... parçalarını mantıksal sırada aç.
        names = [self.file_path]
        i = 0
        while os.path.exists(f"{self.file_path}{i}"):
            names.insert(i, f"{self.file_path}{i}")
            i += 1
        self.data_names = names
        cumulative = 0
        for name in names:
            f = open(name, "rb")
            f.seek(0, os.SEEK_END)
            size = f.tell()
            cumulative += size
            self.data_files.append(f)
            self.data_sizes.append(cumulative)
        self.total_size = cumulative
        self.logger.info("Yedek boyutu: %.2f MiB (%d byte)",
                         self.total_size / (1024 * 1024), self.total_size)

    def find_file_index(self, offset: int) -> int:
        if offset < 0 or offset >= self.total_size:
            raise ValueError(f"Offset sınır dışında: {offset}/{self.total_size}")
        for i, end in enumerate(self.data_sizes):
            if offset < end:
                return i
        raise RuntimeError(f"Offset çözümlenemedi: {offset}")

    def read_bytes(self, offset: int, length: int) -> bytes:
        """Mantıksal offset üzerinden tek veya birden çok parçadan veri okur."""
        if length < 0 or offset < 0 or offset + length > self.total_size:
            raise ValueError(f"Geçersiz okuma aralığı: offset={offset}, length={length}")
        chunks = []
        current = offset
        remaining = length
        while remaining:
            idx = self.find_file_index(current)
            start = current if idx == 0 else current - self.data_sizes[idx - 1]
            available = self.data_sizes[idx] - current
            take = min(remaining, available)
            self.data_files[idx].seek(start)
            chunk = self.data_files[idx].read(take)
            if len(chunk) != take:
                raise OSError("Yedek dosyasından eksik okuma")
            chunks.append(chunk)
            current += take
            remaining -= take
        self.used_ranges.append((offset, length))
        return b"".join(chunks)

    def get_unique_filename(self, path: str) -> str:
        if self.overwrite or not os.path.exists(path):
            return path
        base, ext = os.path.splitext(path)
        n = 1
        while os.path.exists(f"{base}_{n}{ext}"):
            n += 1
        return f"{base}_{n}{ext}"

    @staticmethod
    def strip_pkcs7_padding(data: bytes) -> bytes:
        if not data:
            return data
        pad = data[-1]
        if 1 <= pad <= 16 and len(data) >= pad and data[-pad:] == bytes([pad]) * pad:
            return data[:-pad]
        return data

    def decrypt_aes_ecb(self, data: bytes) -> bytes:
        if not data or len(data) % AES.block_size:
            raise ValueError(f"AES-ECB veri uzunluğu 16'nın katı olmalı: {len(data)}")
        cipher = AES.new(sha256(ENC_KEY).digest(), AES.MODE_ECB)
        return self.strip_pkcs7_padding(cipher.decrypt(data))

    def get_backup_info_size(self, is_new: bool) -> int:
        pos = 1 if is_new else self.total_size - 5
        size = struct.unpack("!L", self.read_bytes(pos, 4))[0]
        if not MIN_HEADER_SIZE <= size <= MAX_HEADER_SIZE:
            raise ValueError(f"Geçersiz başlık uzunluğu: {size}")
        return size

    def parse_header(self, is_new: bool) -> ET.Element:
        label = "NEW" if is_new else "OLD"
        self.logger.info("Başlık ayrıştırılıyor (%s)...", label)
        pos = 5 if is_new else self.total_size - 13
        header_start = struct.unpack("!Q", self.read_bytes(pos, 8))[0]
        size = self.get_backup_info_size(is_new)
        if header_start + size > self.total_size:
            raise ValueError("Başlık yedek dosyasının dışına taşıyor")
        decrypted = self.decrypt_aes_ecb(self.read_bytes(header_start, size))
        text = decrypted.decode("utf-8", errors="ignore").strip("\x00 \r\n\t")
        start = text.find("<?xml")
        if start < 0:
            start = text.find("<")
        if start < 0:
            raise ValueError("Çözülen başlıkta XML bulunamadı")
        text = text[start:]
        path = self.get_unique_filename(os.path.join(self.output_dir, f"header-{label.lower()}.xml"))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        try:
            return ET.fromstring(text)
        except ET.ParseError as exc:
            self.logger.error("XML başlığı geçersiz: %s", exc)
            raise

    def find_attr_by_name(self, name: str) -> Optional[ET.Element]:
        if self.common_header is None:
            return None
        return next((el for el in self.common_header.findall("Attr")
                     if el.get("Name") == name), None)

    def resolve_cg_path(self, name: str) -> str:
        try:
            parts = name.split("_CG_")
            if len(parts) < 2:
                return name
            job, index = parts[0], int(parts[1])
            attr = self.find_attr_by_name(f"KEY_MEDIA_JOB_{job}KEY_MEDIA_TYPE_0")
            if attr is not None and attr.text:
                segments = attr.text.split("@@")
                if 0 <= index < len(segments):
                    return segments[index].replace("@", "")
        except (ValueError, TypeError) as exc:
            self.logger.debug("CG yolu çözümlenemedi (%s): %s", name, exc)
        return name

    def check_lock(self):
        if self.total_size < 33:
            raise ValueError("Yedek dosyası kilit denetimi için çok küçük")
        is_locked = self.read_bytes(self.total_size - 1, 1) != b"\x00"
        if is_locked:
            pw_hash = self.read_bytes(self.total_size - 33, 20).hex()
            self.logger.warning("Yedek kilitli görünüyor. SHA-1 parola özeti: %s", pw_hash)
            self.logger.warning("Bu araç parolayı kırmaz; kendi yedeğinizde parolasız çıkarmayı deneyebilirsiniz.")
        else:
            self.logger.info("Yedek kilitli görünmüyor.")

    def extract_data(self, virtual_path: str, offset: int, length: int,
                     is_missed: bool = False) -> bool:
        if length <= 0:
            return False
        out_path = None
        try:
            # Zip-slip/path traversal ve mutlak yol saldırılarını engelle.
            normalized = virtual_path.replace("\\", "/")
            parts = [p for p in normalized.split("/") if p not in ("", ".", "..")]
            if not parts:
                raise ValueError("Boş veya güvensiz hedef yolu")
            out_path = self.get_unique_filename(os.path.join(self.output_dir, *parts))
            root = os.path.realpath(self.output_dir)
            if os.path.commonpath([root, os.path.realpath(out_path)]) != root:
                raise ValueError("Çıktı dizininin dışına yazma girişimi engellendi")
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            self.used_ranges.append((offset, length))
            if offset < 0 or offset + length > self.total_size:
                raise ValueError("Veri bloğu yedek sınırlarının dışında")
            all_zero = True
            remaining = length
            current = offset
            with open(out_path, "wb") as out:
                while remaining:
                    idx = self.find_file_index(current)
                    start = current if idx == 0 else current - self.data_sizes[idx - 1]
                    take = min(remaining, self.data_sizes[idx] - current, CHUNK_SIZE)
                    self.data_files[idx].seek(start)
                    chunk = self.data_files[idx].read(take)
                    if not chunk:
                        raise OSError("Beklenmeyen dosya sonu")
                    if all_zero and any(chunk):
                        all_zero = False
                    out.write(chunk)
                    remaining -= len(chunk)
                    current += len(chunk)
            if all_zero:
                os.remove(out_path)
                if not is_missed:
                    self.stats["skipped_null"] += 1
                return False
            if not is_missed:
                self.stats["extracted"] += 1
            self.logger.debug("Çıkarıldı: %s (%d byte)", virtual_path, length)
            return True
        except Exception as exc:
            self.logger.error("Çıkarma başarısız (%s): %s", virtual_path, exc)
            if out_path and os.path.exists(out_path):
                try:
                    os.remove(out_path)
                except OSError:
                    pass
            if not is_missed:
                self.stats["failed"] += 1
                self.audit_failed.append({"path": virtual_path, "offset": offset,
                                          "length": length, "reason": str(exc)})
            return False

    def process_items(self):
        if self.root is None:
            return
        items = self.root.findall("BackupItem")
        self.stats["total_items"] = len(items)
        self.logger.info("%d öğe çıkarılıyor...", len(items))
        for index, elem in enumerate(items, 1):
            try:
                category = elem.get("Category", "UNKNOWN")
                if category == "APPLICATION":
                    for app in elem.findall("APPLICATION"):
                        name = app.get("FileName") or app.get("Name") or "unknown.apk"
                        name = os.path.basename(name.replace("\\", "/"))
                        start = int(app.get("StartOffset", 0))
                        size = int(app.get("DataSize", 0))
                        self.extract_data(f"app/{name}", start, size)
                else:
                    file_name = elem.get("FileName", "")
                    target = f"{category}-{file_name}".rstrip("-")
                    if "_CG_" in target and self.try_path_reconstruct:
                        target = "misc/" + self.resolve_cg_path(category).lstrip("/")
                    else:
                        target = "data/" + target
                    self.extract_data(target, int(elem.get("StartOffset", 0)),
                                      int(elem.get("DataSize", 0)))
            except (ValueError, TypeError) as exc:
                self.logger.error("Öğe işlenemedi (%s): %s", elem.get("Category", "?"), exc)
                self.stats["failed"] += 1
            if not self.logger.isEnabledFor(logging.DEBUG) and items:
                print(f"\rİlerleme: {index}/{len(items)} (%{index / len(items) * 100:.1f})",
                      end="", flush=True)
        if items and not self.logger.isEnabledFor(logging.DEBUG):
            print()

    def _merge_ranges(self) -> List[Tuple[int, int]]:
        merged: List[List[int]] = []
        for start, length in sorted(self.used_ranges):
            end = start + length
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            elif end > merged[-1][1]:
                merged[-1][1] = end
        return [(start, end) for start, end in merged]

    def extract_unmapped(self):
        if not self.extract_unmapped_enabled:
            self.logger.info("Eşlenmemiş blok taraması atlandı (--no-unmapped).")
            return
        self.logger.info("Eşlenmemiş veri blokları taranıyor...")
        merged = self._merge_ranges()
        tail_end = max(0, self.total_size - TRAILER_SIZE)
        pos = 1
        for start, end in merged:
            if start > pos:
                name = f"missed/{pos}-{start - 1}.dat"
                if self.extract_data(name, pos, start - pos, is_missed=True):
                    self.stats["missed_blocks"] += 1
                    self.audit_missed.append({"name": name, "size": start - pos})
            pos = max(pos, end)
        if pos < tail_end:
            name = f"missed/{pos}-{tail_end - 1}.dat"
            if self.extract_data(name, pos, tail_end - pos, is_missed=True):
                self.stats["missed_blocks"] += 1
                self.audit_missed.append({"name": name, "size": tail_end - pos})

    def generate_summary(self):
        self.logger.info("=" * 60)
        self.logger.info("DENETİM ÖZETİ")
        for key, value in self.stats.items():
            self.logger.info("  %-16s: %d", key, value)
        for item in self.audit_failed:
            self.logger.info("  [FAIL] %s (offset=%s, uzunluk=%s): %s",
                             item["path"], item["offset"], item["length"], item["reason"])
        for item in self.audit_missed:
            self.logger.info("  [MISSED] %s (%d byte)", item["name"], item["size"])
        self.logger.info("=" * 60)

    def run(self):
        self.check_lock()
        # --force-new/--force-old: varsayılan biçim seçilir, başarısızsa diğer biçim denenir.
        preferred_new = True if self.force_new_header else False if self.force_old_header else True
        try:
            self.root = self.parse_header(preferred_new)
        except Exception as first_error:
            self.logger.warning("İlk başlık biçimi başarısız (%s); diğer biçim deneniyor.", first_error)
            self.root = self.parse_header(not preferred_new)
        self.common_header = self.root.find("Common")
        if self.common_header is None:
            raise RuntimeError("Yedek başlığında 'Common' XML bloğu bulunamadı.")
        is_new = self.common_header.find("IsNew")
        if not self.force_new_header and not self.force_old_header and is_new is not None and is_new.text == "True":
            try:
                new_root = self.parse_header(True)
                new_common = new_root.find("Common")
                if new_common is not None:
                    self.root, self.common_header = new_root, new_common
            except Exception as exc:
                self.logger.warning("Yeni biçim yeniden okunamadı; mevcut başlık kullanılacak: %s", exc)
        self.process_items()
        self.extract_unmapped()
        self.generate_summary()
        self.logger.info("İşlem tamamlandı.")


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="lbf-extractor",
        description=f"LG Backup (.lbf) extractor v{__version__} — {__author__}",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("file", help=".lbf yedek dosyasının yolu")
    parser.add_argument("-o", "--output", default="./export", help="Çıktı dizini")
    parser.add_argument("--no-path-reconstruct", action="store_true", help="CG medya yolunu yeniden oluşturma")
    parser.add_argument("--force-new", action="store_true", help="Yeni başlık biçimini zorla")
    parser.add_argument("--force-old", action="store_true", help="Eski başlık biçimini zorla")
    parser.add_argument("--no-unmapped", action="store_true", help="Eşlenmemiş blokları tarama")
    parser.add_argument("--overwrite", action="store_true", help="Var olan dosyaların üzerine yaz")
    parser.add_argument("--debug", action="store_true", help="Ayrıntılı hata ayıklama günlüğü")
    parser.add_argument("--log", metavar="FILE", help="Ayrıntılı günlüğü dosyaya da yaz")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()
    try:
        with LBFExtractor(args.file, args.output,
                          try_path_reconstruct=not args.no_path_reconstruct,
                          force_new_header=args.force_new, force_old_header=args.force_old,
                          overwrite=args.overwrite, extract_unmapped=not args.no_unmapped,
                          debug=args.debug, log_file=args.log) as extractor:
            extractor.run()
        return 0
    except KeyboardInterrupt:
        print("\nKullanıcı tarafından durduruldu.", file=sys.stderr)
        return 130
    except Exception as exc:
        logging.getLogger("LBFExtractor").critical("Kritik hata: %s", exc)
        if args.debug:
            import traceback
            traceback.print_exc()
        else:
            print("İpucu: ayrıntılı traceback için --debug kullanın.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
