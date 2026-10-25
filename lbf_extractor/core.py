import datetime,logging,os,platform,sys
from pathlib import Path
from typing import BinaryIO,Dict,List,Optional,Tuple
from .common import CHUNK_SIZE,LOGGER_NAME,__author__,__version__,AuditRecord,ColoredFormatter,CorruptedArchiveError,ExtractionStats,Terminal
from .archive import ArchiveMixin
from .paths import PathMixin
from .metadata import MetadataMixin
from .extraction import ExtractionMixin
from .reporting import ReportingMixin
class LBFExtractor(ArchiveMixin,PathMixin,MetadataMixin,ExtractionMixin,ReportingMixin):
    def __init__(
        self,
        file_path: str,
        output_dir: str = "./export",
        try_path_reconstruct: bool = True,
        force_new_header: bool = False,
        force_old_header: bool = False,
        split_lbf_first: bool = False,
        overwrite: bool = False,
        extract_unmapped: bool = True,
        debug: bool = False,
        log_file: Optional[str] = None,
        chunk_size: int = CHUNK_SIZE,
        extract_files: bool = True,
    ) -> None:
        if not file_path.lower().endswith(".lbf"):
            raise ValueError(f"Target must be a valid .lbf archive: {file_path}")
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive bytes")
        if force_new_header and force_old_header:
            raise ValueError(
                "Parameters --force-new and --force-old are mutually exclusive."
            )

        global _INSTANCE_COUNTER
        _INSTANCE_COUNTER += 1
        self._instance_seq = _INSTANCE_COUNTER

        self.archive_path = Path(file_path).resolve()
        self.output_dir = Path(output_dir).resolve()
        self.try_path_reconstruct = try_path_reconstruct
        self.force_new_header = force_new_header
        self.force_old_header = force_old_header
        self.split_lbf_first = split_lbf_first
        self.overwrite = overwrite
        self.extract_unmapped_enabled = extract_unmapped
        self.debug = debug
        self.chunk_size = int(chunk_size)
        self.extract_files_enabled = extract_files

        # Streaming state
        self.part_paths: List[Path] = []
        self.file_handles: List[BinaryIO] = []
        self.part_boundaries: List[int] = []
        self.total_size: int = 0
        self.used_ranges: List[Tuple[int, int]] = []

        # XML metadata
        self.root: Optional[ET.Element] = None
        self.common_header: Optional[ET.Element] = None
        self.header_format: Optional[str] = None  # "new" | "old"

        # Stats & audit
        self.stats = ExtractionStats()
        self.audit_failed: List[AuditRecord] = []
        self.audit_missed: List[Dict[str, int]] = []
        self.start_time: Optional[datetime.datetime] = None
        self.end_time: Optional[datetime.datetime] = None

        self.logger = self._init_logger(debug, log_file)

    # ---- logging ----------------------------------------------------------

    def _init_logger(self, debug: bool, log_file: Optional[str]) -> logging.Logger:
        # Per-instance logger name prevents accidental handler clobbering
        # when multiple extractors coexist (e.g. in a library context).
        logger = logging.getLogger(f"{LOGGER_NAME}.{self._instance_seq}")
        logger.setLevel(logging.DEBUG)
        logger.propagate = False
        logger.handlers.clear()

        console = logging.StreamHandler(sys.stdout)
        console.setLevel(logging.DEBUG if debug else logging.INFO)
        console.setFormatter(ColoredFormatter())
        logger.addHandler(console)

        if log_file:
            fh = logging.FileHandler(log_file, mode="w", encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(
                logging.Formatter(
                    "%(asctime)s [%(levelname)-8s] "
                    "<%(filename)s:%(lineno)d> %(message)s"
                )
            )
            logger.addHandler(fh)

        return logger

    # ---- context manager --------------------------------------------------

    def __enter__(self) -> "LBFExtractor":
        Terminal.init()
        self.start_time = datetime.datetime.now()
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if any(self.output_dir.iterdir()):
            self.logger.warning(
                "Export destination is not empty. Existing files will be "
                "versioned to avoid collisions."
            )

        try:
            self._load_archive_segments()
        except Exception:
            self._cleanup()
            raise

        self._print_banner()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._cleanup()
        self.end_time = datetime.datetime.now()

    def _cleanup(self) -> None:
        """Close file handles and detach the logger's handlers (idempotent)."""
        for fh in self.file_handles:
            try:
                fh.close()
            except OSError:
                pass
        self.file_handles.clear()

        for h in self.logger.handlers[:]:
            try:
                h.close()
            except Exception:
                pass
            self.logger.removeHandler(h)

    # ---- banners / segment discovery -------------------------------------

    def _print_banner(self) -> None:
        print(
            f"{Terminal.CYAN}{Terminal.BOLD}LG Backup Extractor (lbf-extractor){Terminal.RESET} "
            f"v{__version__} by {__author__}\n"
            f"Archive: {Terminal.style(self.archive_path.name, Terminal.BOLD)} "
            f"({self.total_size / (1024 * 1024):,.2f} MiB across "
            f"{len(self.part_paths)} part(s))\n"
            f"{Terminal.DIM}Platform: {platform.system()} {platform.release()} | "
            f"Python: {platform.python_version()}{Terminal.RESET}\n"
        )
        if len(self.part_paths) > 1:
            self.logger.info("Multipart slice assembly order:")
            for idx, p in enumerate(self.part_paths):
                self.logger.info(
                    "  [%d] %s (%s bytes)", idx, p.name, f"{p.stat().st_size:,}"
                )

    def execute(self) -> None:
        """Run the complete extraction pipeline."""
        self.check_lock_status()

        preferred_new = (
            True if self.force_new_header
            else False if self.force_old_header
            else True
        )

        try:
            self.root = self.parse_header(preferred_new)
        except Exception as primary_err:
            self.logger.warning(
                "Primary header parse failed (%s); trying alternate scheme...",
                primary_err,
            )
            self.root = self.parse_header(not preferred_new)

        self.common_header = self.root.find("Common")
        if self.common_header is None:
            raise CorruptedArchiveError(
                "Corrupted XML metadata: <Common> descriptor missing from header root."
            )

        is_new_el = self.common_header.find("IsNew")
        if (
            not self.force_new_header
            and not self.force_old_header
            and self.header_format != "new"
            and is_new_el is not None
            and is_new_el.text == "True"
        ):
            try:
                new_root = self.parse_header(True)
                new_common = new_root.find("Common")
                if new_common is not None:
                    self.root, self.common_header = new_root, new_common
            except Exception as err:
                self.logger.debug(
                    "Automated header realignment bypassed: %s", err
                )

        # Mark byte 0 as consumed for the modern format so the orphan
        # scanner does not emit a spurious 1-byte "block_0x00000000".
        if self.header_format == "new":
            self.used_ranges.append((0, 1))

        from .diagnostics import write_metadata_report
        report_path = write_metadata_report(self)
        self.logger.info("Metadata report written: %s", report_path)
        if self.extract_files_enabled:
            self.process_items()
            self.extract_unmapped_regions()
        else:
            self.logger.info("Metadata-only mode: file extraction is disabled.")
        self.end_time = datetime.datetime.now()
        self.print_summary_box()
        self.logger.info("Extraction completed successfully.")
