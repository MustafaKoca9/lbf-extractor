# Architecture overview

## Current layout

The extractor is intentionally kept in the top-level `lbf_extractor.py` module at this stage. This preserves existing usage such as `from lbf_extractor import LBFExtractor` and the source-file entry point while packaging and automated tests make changes easier to validate.

| Path | Responsibility |
| --- | --- |
| `lbf_extractor.py` | CLI, archive segment handling, header parsing, decryption, safe path resolution, streaming extraction, audit summary. |
| `tests/test_helpers.py` | Deterministic tests for padding handling. |
| `tests/test_cli.py` | CLI defaults, optional flags, and constructor validation. |
| `examples/usage.md` | Realistic command-line and Python API examples. |
| `pyproject.toml` | Package metadata, dependencies, CLI entry point, and developer tooling. |
| `.github/workflows/tests.yml` | Automated tests across supported Python versions. |

## Extraction flow

1. The CLI validates arguments and creates an `LBFExtractor`.
2. The extractor discovers multipart segments and opens them as a logical byte stream.
3. Archive boundaries and header metadata are checked before data is interpreted.
4. The header is decrypted, unpadded, decoded, and parsed as XML.
5. Catalog entries are streamed to confined output paths; failures are recorded.
6. Optionally, ranges not covered by catalog entries are written to `unmapped/`.
7. A summary and audit records are printed for review.

## Important invariants

- Do not load a complete backup into memory; keep the streaming design.
- Validate every untrusted offset and length before reading.
- Keep output paths confined to the selected destination.
- Preserve deterministic behavior for split segment ordering.
- Never use a real person's backup as a public test fixture.
- Keep the public `LBFExtractor` import and `lbf-extractor` command compatible unless the change is documented as breaking.

## Safe refactoring direction

If the implementation grows, extract well-defined responsibilities into modules in small steps: CLI and argument validation, segment/stream reader, header and XML parser, path policy, and audit/reporting. Add tests before moving behavior and keep the current top-level import as a compatibility facade. Avoid a large file split without fixtures that cover both header formats and multipart reads.
