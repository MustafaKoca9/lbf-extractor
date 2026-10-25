"""Public API; CLI is optional."""
from .common import __author__, __license__, __repository__, __version__, AuditRecord, ExtractionStats, LBFExtractorError, SecurityError, CorruptedArchiveError
from .core import LBFExtractor

def extract_archive(file_path, output_dir="./export", **options):
    """Extract with defaults without invoking the CLI."""
    with LBFExtractor(file_path=file_path, output_dir=output_dir, **options) as extractor:
        extractor.execute()
    return extractor

__all__ = ["LBFExtractor", "extract_archive", "ExtractionStats", "AuditRecord", "LBFExtractorError", "SecurityError", "CorruptedArchiveError", "__version__", "__author__", "__license__", "__repository__"]
