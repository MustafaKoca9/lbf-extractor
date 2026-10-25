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
