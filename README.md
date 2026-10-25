# lbf-extractor

> **LG Mobile Switch (`.lbf`) backup inspector and forensic extractor.**

[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-lightgrey.svg)]()
[![Status](https://img.shields.io/badge/status-stable-brightgreen.svg)]()

A streaming unpacker and decryptor for **LG Mobile Switch** `.lbf` backup archives.
Recovers application packages, internal databases, media, and forensic orphan
blocks without loading the entire backup into memory.

> ⚠️ **Use only on backups you own.** This tool is intended for personal data
> recovery and digital forensics on your own devices. See the [legal](#legal--ethics)
> section before using it.

---

## Features

- **Streaming architecture** — arbitrary file sizes, split `.lbf` sets supported,
  ~1 MiB working set regardless of backup size.
- **Dual header engine** — auto-detects modern header (new `IsNew=True` scheme)
  and legacy trailer format.
- **AES-128-ECB decryption** with a SHA-256-derived key and PKCS#7 unpadding.
- **Path-traversal safe** — token filter *and* canonical `commonpath` confinement;
  every failure recorded.
- **Forensic orphan recovery** — unreferenced byte ranges are dumped to
  `unmapped/block_0x…_0x….bin` for carving.
- **Zero heavyweight dependencies** — only `pycryptodome`.

---

## Requirements

- Python **3.9+**
- [`pycryptodome`](https://pypi.org/project/pycryptodome/)

```bash
pip install pycryptodome
```

---

Installation

As a CLI tool (recommended)

```bash
git clone https://github.com/mustafakoca/lbf-extractor.git
cd lbf-extractor
pip install .
lbf-extractor --help
```

As a library

```python
from lbf_extractor import LBFExtractor

with LBFExtractor("my_backup.lbf", output_dir="./recovered") as ex:
    ex.execute()
```

---

Quick start

```bash
# Single-file backup
lbf-extractor my_backup.lbf -o ./recovered

# Split backup (.lbf0, .lbf1, …, .lbf)
lbf-extractor my_backup.lbf -o ./recovered --debug

# Split backup with .lbf as the FIRST segment
lbf-extractor my_backup.lbf --split-lbf-first

# Forensic mode: keep everything, verbosely
lbf-extractor my_backup.lbf -o ./recovered --debug --log run.log
```

Running from source without installing

```bash
python lbf_extractor.py my_backup.lbf -o ./recovered
```

---

Output layout

```
recovered/
├── header-new.xml                 # decrypted header (kept for auditing)
├── app/                           # .apk packages
├── media/                         # reconstructed media paths (CG_ resolution)
├── records/                       # categorized data records
└── unmapped/
    └── block_0x000002A0_0x00001FFF.bin   # orphan/forensic byte ranges
```

Use --no-unmapped to skip the orphan scan, --no-path-reconstruct to
disable the media/ path inference, or --overwrite to replace existing files
instead of versioning them (file.txt → file_1.txt).

---

CLI reference

Flag Default Description
file — Path to .lbf (or primary segment). Required.
-o, --output ./export Output directory.
--no-path-reconstruct off Disable CG-media path inference.
--force-new auto Force new-format header parse.
--force-old auto Force old-format header parse.
--split-lbf-first off Assemble .lbf first (default: .lbf last).
--no-unmapped off Skip orphan raw-block dump.
--overwrite off Overwrite existing files.
--debug off Verbose logging.
--log FILE — Mirror logs to a file.
-v, --version — Print version.

--force-new and --force-old are mutually exclusive.

---

How it works

LG .lbf files store most data in an AES-128-ECB encrypted XML header describing
BackupItem entries with StartOffset / DataSize pointers into the archive
body. lbf-extractor:

1. Reads the trailing/leading header pointer depending on format version.
2. Decrypts the header using sha256(ENC_KEY).digest() as the AES key.
3. Enumerates BackupItem entries and streams their byte ranges to disk.
4. Merges all read ranges and dumps leftover ranges as forensic blocks.

The AES key is a fixed constant of the file format as observed in LG Mobile
Switch output. If LG changes it in a future release, this tool will stop working
until the new key is extracted.

---

Legal & ethics

· Use only on backups you own or have explicit legal authorisation to examine.
· The encryption key is a documented format constant recovered via reverse
  engineering of LG Mobile Switch output; no DRM, no protected content, and no
  other user's data are decrypted by design.
· The author provides no warranty; results may be incomplete or corrupted.
  See LICENSE.
· If you find a security issue in this tool, please read SECURITY.md.

---

Development

```bash
git clone https://github.com/mustafakoca/lbf-extractor.git
cd lbf-extractor
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest -v
```

See CONTRIBUTING.md for the coding style, commit-message
convention and PR checklist.

---

Changelog

See CHANGELOG.md.

---

License

MIT © Mustafa Koca — see LICENSE.
