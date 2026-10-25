# Architecture

This is a Python library. There is no command-line interface.

| Module | Responsibility |
| --- | --- |
| `common.py` | Shared constants, exceptions, result models, terminal output, and version metadata. |
| `archive.py` | Reads the full logical archive into memory and provides direct byte-range reads. |
| `metadata.py` | Decrypts and parses header metadata. |
| `paths.py` | Resolves output filenames and writes complete byte/text values directly. |
| `extraction.py` | Extracts complete catalog payload ranges and optionally recovers unmapped ranges. |
| `diagnostics.py` | Produces JSON/Markdown reports retaining raw XML and unknown attributes. |
| `reporting.py` | Formats the final summary. |
| `core.py` | Coordinates the components through the public `LBFExtractor` API. |

## Data flow

1. `ArchiveReader` loads the primary archive and any numbered companion segments into one `bytes` value.
2. `MetadataParser` reads the header ranges, decrypts the header, and returns its XML tree.
3. `diagnostics.py` records the raw XML, attributes, and parsed offset/size fields.
4. `PayloadExtractor` reads each payload range in one operation and writes it as one complete file.
5. If enabled, the unmapped-range scan recovers gaps not referenced by the catalog.

## Trade-off

This deliberately favors straightforward whole-range processing over streaming. Memory use can approach the size of the complete archive plus the largest payload being written. Use it with enough available RAM for the backup you are inspecting.
