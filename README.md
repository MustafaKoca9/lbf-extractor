# lbf-extractor

[English](README.md) · [Türkçe](README.tr.md)

> A streaming inspector and extractor for LG Mobile Switch `.lbf` backups.

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![MIT License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platforms](https://img.shields.io/badge/platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)]()

`lbf-extractor` reads LG Mobile Switch backup archives, decrypts their metadata, streams referenced files to an output directory, and can preserve unreferenced byte ranges for forensic review. It is designed to avoid loading the entire archive into memory.

**Use only backups you own or are explicitly authorized to examine.** See [SECURITY.md](SECURITY.md) and the [legal notes](#responsible-use).

## What it does

- Streams archive data in 1 MiB chunks, including multipart backups.
- Detects the newer header layout and the legacy trailer layout.
- Decrypts the archive metadata with AES-128-ECB and removes valid PKCS#7 padding.
- Reconstructs media paths when metadata provides enough information.
- Can write unreferenced byte ranges to `unmapped/` for later forensic analysis.
- Checks output paths to reduce directory-traversal risk and records extraction failures.
- Offers both a command-line interface and a Python API.

Runtime dependency: [PyCryptodome](https://pypi.org/project/pycryptodome/). Python 3.9 or newer is required.

## Install

### Install as a command-line tool

```bash
git clone https://github.com/MustafaKoca9/lbf-extractor.git
cd lbf-extractor
python -m pip install .
lbf-extractor --help
```

### Run from a source checkout

```bash
python -m pip install -r requirements.txt
python lbf_extractor.py phone_backup.lbf --output ./recovered
```

## Quick start

```bash
# Extract a single-file backup
lbf-extractor phone_backup.lbf --output ./recovered

# Show detailed logs and save them to a file
lbf-extractor phone_backup.lbf --output ./recovered --debug --log run.log

# Do not write unreferenced byte ranges
lbf-extractor phone_backup.lbf --output ./recovered --no-unmapped

# If the .lbf file is the first multipart segment
lbf-extractor phone_backup.lbf --split-lbf-first
```

For multipart backups, point the program at the `.lbf` file. By default, it looks for adjacent `.lbf0`, `.lbf1`, … segments and assembles them in the usual order: numbered segments first, the `.lbf` file last. Use `--split-lbf-first` only when your backup uses the opposite convention.

## Use as a Python library

```python
from lbf_extractor import LBFExtractor

with LBFExtractor("phone_backup.lbf", output_dir="./recovered") as extractor:
    extractor.execute()

print("Extracted:", extractor.stats.extracted)
print("Failed:", extractor.stats.failed)
```

The context manager closes open segment files and logging handlers. Extraction results and failures are available through `extractor.stats`, `extractor.audit_failed`, and `extractor.audit_missed`.

## Output layout

The exact file names depend on the backup metadata. A typical output can include:

```text
recovered/
├── header-new.xml
├── app/
├── media/
├── records/
└── unmapped/
```

The `unmapped/` directory contains raw ranges not referenced by the parsed metadata. These ranges are not guaranteed to be valid or complete files.

## Command-line options

| Option | Description |
| --- | --- |
| `file` | Required path to the primary `.lbf` file. |
| `-o, --output DIR` | Output directory; default: `./export`. |
| `--no-path-reconstruct` | Disable media path reconstruction. |
| `--force-new` | Force the newer header format. |
| `--force-old` | Force the legacy header format. |
| `--split-lbf-first` | Place the `.lbf` segment before numbered segments. |
| `--no-unmapped` | Skip recovery of unreferenced ranges. |
| `--overwrite` | Replace existing output files rather than versioning collisions. |
| `--debug` | Enable verbose logging. |
| `--log FILE` | Also write detailed logs to a file. |
| `-v, --version` | Print the installed version. |

`--force-new` and `--force-old` cannot be used together. Run `lbf-extractor --help` for the authoritative help text.

## Development

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e ".[dev]"
pytest -q
python -m py_compile lbf_extractor.py
```

- [Architecture overview](docs/architecture.md)
- [Usage examples](examples/usage.md)
- [Contributing guide](CONTRIBUTING.md)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

The repository keeps the current extractor in one module to preserve the public import and CLI while the tests and packaging are established. See the architecture guide for boundaries to keep in mind when making larger changes.

## Responsible use

- Process only backups you own or have explicit permission to inspect.
- Treat extracted messages, media, databases, XML, and logs as sensitive personal data.
- Do not publish real backup files, keys, personal paths, or extracted records in issues or pull requests.
- Extraction may be incomplete or produce damaged files. Always keep an untouched copy of the original backup.

## License

MIT. See [LICENSE](LICENSE).
