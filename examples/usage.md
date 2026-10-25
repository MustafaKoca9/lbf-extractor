# Usage examples

This guide complements the main [README](../README.md). Use the same primary `.lbf` path you would pass to the command-line tool.

## 1. Extract a backup

```bash
lbf-extractor phone_backup.lbf --output ./recovered
```

The destination may contain a decrypted header, application packages, reconstructed media paths, categorized records, and (unless disabled) unreferenced byte ranges. Names depend on the backup metadata.

## 2. Inspect a multipart backup

LG Mobile Switch backups may be split into `.lbf0`, `.lbf1`, and `.lbf` parts. The default assembly order is numbered parts first, with `.lbf` last. Pass the primary `.lbf` path:

```bash
lbf-extractor phone_backup.lbf --output ./recovered --debug
```

For a backup whose `.lbf` segment comes first:

```bash
lbf-extractor phone_backup.lbf --split-lbf-first
```

Review the debug output to confirm the segment order before relying on recovered data.

## 3. Keep a forensic log

```bash
lbf-extractor phone_backup.lbf --output ./forensics --debug --log run.log
```

Use `--no-unmapped` to skip raw ranges that are not referenced by metadata. Otherwise, those ranges are written under `unmapped/` using their byte offsets in the file name. They may require separate carving tools and are not guaranteed to represent complete files.

For plain-text terminal output, set `NO_COLOR=1`:

```bash
NO_COLOR=1 lbf-extractor phone_backup.lbf --output ./forensics --debug --log run.log
```

Redact personal paths and metadata before sharing logs.

## 4. Use the Python API

```python
from lbf_extractor import LBFExtractor

with LBFExtractor(
    "phone_backup.lbf",
    output_dir="./recovered",
    try_path_reconstruct=True,
    overwrite=False,
    extract_unmapped=True,
    debug=False,
    log_file="run.log",
) as extractor:
    extractor.execute()

print("Extracted:", extractor.stats.extracted)
print("Failed:", extractor.stats.failed)

for record in extractor.audit_failed:
    print(record)
```

## 5. Help with a bug report

Collect the version and environment information:

```bash
lbf-extractor --version
python --version
python -c "import platform; print(platform.platform())"
```

Include the exact command and a redacted `--debug` trace. Do not attach a real backup or recovered personal content. Prefer a synthetic reproduction.
