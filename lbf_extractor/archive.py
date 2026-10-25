"""Independent reader for single-part and multipart LBF archives."""
from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import BinaryIO, Iterator, List, Tuple, Union

from .common import CHUNK_SIZE, CorruptedArchiveError


class ArchiveReader:
    """Own archive file handles and expose a logical, bounded byte stream."""

    def __init__(
        self,
        archive_path: Union[str, Path],
        split_lbf_first: bool = False,
    ) -> None:
        self.archive_path = Path(archive_path).expanduser().resolve()
        self.split_lbf_first = split_lbf_first
        self.part_paths: List[Path] = []
        self.file_handles: List[BinaryIO] = []
        self.part_boundaries: List[int] = []
        self.used_ranges: List[Tuple[int, int]] = []
        self.total_size = 0
        self._opened = False

    def open(self) -> "ArchiveReader":
        if self._opened:
            return self

        self.part_paths.clear()
        self.file_handles.clear()
        self.part_boundaries.clear()
        self.used_ranges.clear()
        self.total_size = 0

        if not self.archive_path.is_file():
            raise FileNotFoundError(f"Primary LBF archive does not exist: {self.archive_path}")

        pattern = re.compile(re.escape(self.archive_path.name) + r"(\d+)$")
        slices_by_index = {}
        for candidate in self.archive_path.parent.iterdir():
            match = pattern.fullmatch(candidate.name)
            if match and candidate.is_file():
                index = int(match.group(1))
                if index in slices_by_index:
                    raise CorruptedArchiveError(
                        f"Duplicate numbered archive segment index: {index}"
                    )
                slices_by_index[index] = candidate

        if slices_by_index:
            indices = sorted(slices_by_index)
            expected = list(range(indices[-1] + 1))
            if indices != expected:
                missing = sorted(set(expected).difference(indices))
                raise CorruptedArchiveError(
                    "Numbered archive segments are not contiguous; "
                    f"missing segment(s): {missing}"
                )

        slices = [slices_by_index[index] for index in sorted(slices_by_index)]
        paths = [self.archive_path] + slices if self.split_lbf_first else slices + [self.archive_path]

        cumulative = 0
        try:
            for path in paths:
                handle = open(path, "rb")
                self.file_handles.append(handle)
                handle.seek(0, os.SEEK_END)
                cumulative += handle.tell()
                self.part_boundaries.append(cumulative)
        except OSError:
            self.close()
            raise

        if cumulative <= 0:
            self.close()
            raise CorruptedArchiveError("The archive contains no data.")

        self.part_paths = paths
        self.total_size = cumulative
        self._opened = True
        return self

    def close(self) -> None:
        for handle in self.file_handles:
            try:
                handle.close()
            except OSError:
                pass
        self.file_handles.clear()
        self._opened = False

    def __enter__(self) -> "ArchiveReader":
        return self.open()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if not self._opened:
            raise RuntimeError("ArchiveReader must be opened before reading.")

    def _find_slice_index(self, offset: int) -> int:
        if offset < 0 or offset >= self.total_size:
            raise IndexError(
                f"Logical offset outside archive: {offset:,} / {self.total_size:,}"
            )
        for index, boundary in enumerate(self.part_boundaries):
            if offset < boundary:
                return index
        raise RuntimeError(f"Unable to map logical offset {offset} to a segment")

    def iter_range(
        self,
        offset: int,
        length: int,
        chunk_size: int = CHUNK_SIZE,
    ) -> Iterator[bytes]:
        """Yield exactly the requested range in bounded chunks across segments."""
        self._ensure_open()
        if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")
        if length < 0 or offset < 0 or offset > self.total_size or length > self.total_size - offset:
            raise ValueError(
                f"Invalid archive range: offset={offset:,}, length={length:,}, "
                f"archive_size={self.total_size:,}"
            )

        remaining = length
        cursor = offset
        while remaining > 0:
            index = self._find_slice_index(cursor)
            slice_start = cursor if index == 0 else cursor - self.part_boundaries[index - 1]
            available = self.part_boundaries[index] - cursor
            take = min(remaining, available, chunk_size)

            handle = self.file_handles[index]
            handle.seek(slice_start)
            chunk = handle.read(take)
            if not chunk:
                raise OSError(
                    f"Unexpected early EOF in segment {self.part_paths[index].name!r}."
                )

            cursor += len(chunk)
            remaining -= len(chunk)
            yield chunk

    def read_bytes(self, offset: int, length: int) -> bytes:
        """Read a range into memory and record it as consumed metadata bytes."""
        if length == 0:
            self._ensure_open()
            if offset < 0 or offset > self.total_size:
                raise ValueError(f"Invalid zero-length read at offset {offset}.")
            return b""

        result = bytearray()
        for chunk in self.iter_range(offset, length, CHUNK_SIZE):
            result.extend(chunk)
        self.used_ranges.append((offset, length))
        return bytes(result)
