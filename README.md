# lbf-extractor

[English](README.md) | [Türkçe](README.tr.md)

A modular streaming inspector and recovery library for LG Mobile Switch LBF backups. The core API does not depend on the optional CLI. Successful header parsing produces metadata_report.json and metadata_report.md, including parsed XML, original field values, and unresolved fields.

Install with: python -m pip install .
Run: lbf-extractor backup.lbf --output ./recovered
Metadata only: lbf-extractor backup.lbf --output ./report --metadata-only
Change stream chunk size: lbf-extractor backup.lbf --chunk-size-mib 4

Library API: from lbf_extractor import extract_archive; call extract_archive("backup.lbf", "./recovered"). To skip payload extraction use extract_archive("backup.lbf", "./report", extract_files=False). API chunk_size is measured in bytes.

Reports may contain sensitive personal data; redact before sharing. See docs/architecture.md. Development: python -m pip install -e ".[dev]" then pytest -q. MIT license.
