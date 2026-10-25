# lbf-extractor

[English](README.md) | [Türkçe](README.tr.md)

A Python library for inspecting and extracting LG Mobile Switch `.lbf` backups. The API reads the complete logical archive into memory, then writes each catalog payload as a complete byte range. Numbered companion segments are combined into the same logical archive when present.

A successful header parse produces `metadata_report.json` and `metadata_report.md`, including parsed XML, original field values, and unresolved fields.

## Usage

```python
from lbf_extractor import extract_archive

extractor = extract_archive("backup.lbf", "./recovered")
print(extractor.stats)
```

To create metadata reports without extracting payloads:

```python
from lbf_extractor import extract_archive

extractor = extract_archive("backup.lbf", "./report", extract_files=False)
```

Install with `python -m pip install .`. See `docs/architecture.md`. MIT license.
