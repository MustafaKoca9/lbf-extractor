# lbf-extractor

A Python utility for inspecting and extracting files from LG Mobile Switch `.lbf` backups. It decrypts the backup header, parses its XML metadata, exports application and data entries, supports multipart backups, and can optionally recover unreferenced byte ranges.

> **Important:** This project is reverse-engineered and has not been validated against every LG backup variant. Test it on a copy of a backup you own. Keep the original backup untouched. Unmapped recovery may produce opaque `.dat` files rather than recognizable files.

## Features

- AES-ECB header decryption using a SHA-256-derived key
- Automatic fallback between the legacy and newer header formats
- Multipart backup reading (`.lbf`, `.lbf0`, `.lbf1`, …)
- 1 MiB streaming extraction to limit memory use
- Optional recovery of data ranges not referenced by XML metadata
- Optional CG media path reconstruction
- Collision-safe filenames by default, with opt-in `--overwrite`
- Lock-state diagnostics, progress reporting, audit summary, and debug logs
- Output-path validation to reduce path traversal risk from untrusted backup metadata

## Requirements

- Python 3.9 or newer
- `pycryptodome`

## Installation

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows PowerShell, activate the environment with `.venv\\Scripts\\Activate.ps1`.

## Usage

```bash
python lbf_extractor.py backup.lbf
python lbf_extractor.py backup.lbf -o ./recovered --debug --log run.log
python lbf_extractor.py backup.lbf --no-unmapped --no-path-reconstruct
python lbf_extractor.py backup.lbf --overwrite
python lbf_extractor.py --help
python lbf_extractor.py --version
```

Keep all multipart files (`.lbf`, `.lbf0`, `.lbf1`, …) together with their original names. Use only backups you own or are authorized to examine. Extracted files may contain sensitive personal data; store output securely and do not publish backup contents or metadata.

## Limitations

This is a reverse-engineered format-specific tool, not a general Android backup utility. It does not crack backup passwords and has not been validated against every LG firmware/application version. Validate it against copies of your own backups before relying on recovered data.

## License

MIT. See [`LICENSE`](LICENSE).
