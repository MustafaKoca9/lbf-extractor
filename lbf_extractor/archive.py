"""Read an LBF archive into memory, including numbered companion segments."""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple, Union

from .common import CorruptedArchiveError


class ArchiveReader:
    """Represent the complete logical archive as one in-memory bytes object."""

    def __init__(self, archive_path: Union[str, Path], split_lbf_first: bool = False) -> None:
        self.archive_path = Path(archive_path).expanduser().resolve()
        self.split_lbf_first = split_lbf_first
        self.part_paths: List[Path] = []
        self.part_boundaries: List[int] = []
        self.used_ranges: List[Tuple[int, int]] = []
        self.total_size = 0
        self.data = b""
        self._opened = False

    def open(self) -> "ArchiveReader":
        if self._opened:
            return self
        if not self.archive_path.is_file():
            raise FileNotFoundError(f"Primary LBF archive does not exist: {self.archive_path}")

        pattern = re.compile(re.escape(self.archive_path.name) + r"(\d+)$")
        slices_by_index = {}
        for candidate in self.archive_path.parent.iterdir():
            match = pattern.fullmatch(candidate.name)
            if match and candidate.is_file():
                slices_by_index[int(match.group(1))] = candidate

        if slices_by_index:
            indices = sorted(slices_by_index)
            expected = list(range(indices[-1] + 1))
            if indices != expected:
                missing = sorted(set(expected).difference(indices))
                raise CorruptedArchiveError(f"Numbered archive segments are missing: {missing}")

        slices = [slices_by_index[index] for index in sorted(slices_by_index)]
        paths = [self.archive_path] + slices if self.split_lbf_first else slices + [self.archive_path]
        chunks = []
        self.part_paths = paths
        self.part_boundaries = []
        total = 0
        for path in paths:
            content = path.read_bytes()
            chunks.append(content)
            total += len(content)
            self.part_boundaries.append(total)

        self.data = b"".join(chunks)
        self.total_size = len(self.data)
        if not self.data:
            raise CorruptedArchiveError("The archive contains no data.")
        self.used_ranges.clear()
        self._opened = True
        return self

    def close(self) -> None:
        self.data = b""
        self._opened = False

    @property
    def is_open(self) -> bool:
        return self._opened

    def __enter__(self) -> "ArchiveReader":
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def read_bytes(self, offset: int, length: int) -> bytes:
        """Return a complete byte range in one operation."""
        if not self._opened:
            raise RuntimeError("ArchiveReader must be opened before reading.")
        if offset < 0 or length < 0 or offset > self.total_size or length > self.total_size - offset:
            raise ValueError(
                f"Invalid archive range: offset={offset}, length={length}, "
                f"archive_size={self.total_size}"
            )
        self.used_ranges.append((offset, length))
        return self.data[offset:offset + length]
