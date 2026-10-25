# Architecture

The package uses composition rather than mixins. The CLI is an optional adapter and is not imported by the core API.

| Module | Responsibility |
| --- | --- |
| `common.py` | Shared constants, public exceptions, result data models, terminal formatting, and version metadata. |
| `archive.py` | `ArchiveReader`: owns segment handles, validates segment ordering, and exposes bounded `iter_range()` / `read_bytes()` APIs. |
| `metadata.py` | `MetadataParser`: decrypts and parses header metadata using an injected archive reader and output manager. |
| `paths.py` | `OutputManager`: confines paths and atomically publishes completed files. |
| `extraction.py` | `PayloadExtractor`: interprets catalog ranges, streams payloads, records failures, and recovers unmapped ranges. |
| `diagnostics.py` | Builds JSON/Markdown metadata reports while retaining raw XML and unknown attributes. |
| `reporting.py` | Stateless terminal summary formatter. |
| `core.py` | Public `LBFExtractor` coordinator and compatibility facade. |
| `cli.py` | Optional command-line argument parsing and exit-code handling. |

## Data flow

1. `LBFExtractor` opens an `ArchiveReader`, which owns all segment file handles.
2. `MetadataParser` reads bounded ranges, decrypts the header, and returns the XML tree.
3. `diagnostics.py` serializes the original tree and records both raw and parsed offset/size values before payload extraction begins.
4. `PayloadExtractor` iterates the catalog and uses `ArchiveReader.iter_range()` to stream data in configurable chunks.
5. `OutputManager` writes into same-directory temporary files and publishes completed outputs atomically.
6. If enabled, the unmapped-range scan merges known ranges and recovers only gaps before the archive trailer.

## Important invariants

- Never load the full archive into memory just to extract a payload.
- Validate offsets and lengths before reading or writing.
- Do not silently skip gaps in numbered multipart segments.
- Keep generated reports and extracted user data private; reports can contain personal information.
- A range that lies within archive bounds is only numerically valid. It may still be interpreted incorrectly for a particular backup format.
- Keep CLI details out of the core parser and archive reader.

API `chunk_size` is measured in bytes. CLI `--chunk-size-mib` is measured in MiB. Use `--metadata-only` to collect diagnostics without writing payload files.
