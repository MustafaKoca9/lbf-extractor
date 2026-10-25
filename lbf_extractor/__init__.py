"""Public API and independently usable extraction components."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Union

from .archive import ArchiveReader
from .common import (
    __author__,
    __license__,
    __repository__,
    __version__,
    AuditRecord,
    CorruptedArchiveError,
    ExtractionStats,
    LBFExtractorError,
)
from .core import LBFExtractor
from .extraction import PayloadExtractor
from .metadata import MetadataParser
from .paths import OutputManager


def extract_archive(
    file_path: Union[str, Path],
    output_dir: Union[str, Path] = "./export",
    **options: Any,
) -> LBFExtractor:
    """Run an extraction and return the closed extractor with its report/stats.

    Use extract_files=False for metadata-only inspection.
    """
    with LBFExtractor(file_path=file_path, output_dir=output_dir, **options) as extractor:
        extractor.execute()
    return extractor


__all__ = [
    "LBFExtractor",
    "extract_archive",
    "ArchiveReader",
    "MetadataParser",
    "OutputManager",
    "PayloadExtractor",
    "ExtractionStats",
    "AuditRecord",
    "LBFExtractorError",
    "CorruptedArchiveError",
    "__version__",
    "__author__",
    "__license__",
    "__repository__",
]
