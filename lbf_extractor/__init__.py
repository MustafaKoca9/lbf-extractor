"""Public Python API; importing the library does not invoke its CLI."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Union

from .common import (
    __author__,
    __license__,
    __repository__,
    __version__,
    AuditRecord,
    CorruptedArchiveError,
    ExtractionStats,
    LBFExtractorError,
    SecurityError,
)
from .core import LBFExtractor


def extract_archive(
    file_path: Union[str, Path],
    output_dir: Union[str, Path] = "./export",
    **options: Any,
) -> LBFExtractor:
    """Run an extraction and return the closed extractor with its report/stats.

    Options are forwarded to LBFExtractor, for example chunk_size=4 * 1024 * 1024
    or extract_files=False for metadata-only inspection.
    """
    with LBFExtractor(file_path=file_path, output_dir=output_dir, **options) as extractor:
        extractor.execute()
    return extractor


__all__ = [
    "LBFExtractor",
    "extract_archive",
    "ExtractionStats",
    "AuditRecord",
    "LBFExtractorError",
    "SecurityError",
    "CorruptedArchiveError",
    "__version__",
    "__author__",
    "__license__",
    "__repository__",
]
