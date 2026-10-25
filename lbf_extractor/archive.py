"""Multipart archive discovery and bounded logical reads."""
from __future__ import annotations

import io
import os
import re
from pathlib import Path
from typing import List

from .common import CorruptedArchiveError


class ArchiveMixin:
    def _load_archive_segments(self) -> None:
        """Open the primary LBF and contiguous numbered segments in logical order.

        The standard order is .lbf0, .lbf1, ..., .lbf. Set split_lbf_first to
        reverse that convention. A numbered gap is rejected rather than silently
        ignoring later segments and producing a corrupt logical archive.
        """
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

        slices: List[Path] = [
            slices_by_index[index] for index in sorted(slices_by_index)
        ]
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
            self._cleanup()
            raise

        if cumulative <= 0:
            self._cleanup()
            raise CorruptedArchiveError("The archive contains no data.")

        self.part_paths = paths
        self.total_size = cumulative

    def _find_slice_index(self, offset: int) -> int:
        if offset < 0 or offset >= self.total_size:
            raise IndexError(
                f"Logical offset outside archive: {offset:,} / {self.total_size:,}"
            )
        for index, boundary in enumerate(self.part_boundaries):
            if offset < boundary:
                return index
        raise RuntimeError(f"Unable to map logical offset {offset} to a segment")

    def read_bytes(self, offset: int, length: int) -> bytes:
        """Read exactly length bytes, including when the range crosses segments."""
        if length < 0 or offset < 0 or offset + length > self.total_size:
            raise ValueError(
                f"Invalid archive range: offset={offset:,}, length={length:,}, "
                f"archive_size={self.total_size:,}"
            )
        if length == 0:
            return b""

        buffer = io.BytesIO()
        remaining = length
        cursor = offset

        while remaining:
            index = self._find_slice_index(cursor)
            slice_start = cursor if index == 0 else cursor - self.part_boundaries[index - 1]
            available = self.part_boundaries[index] - cursor
            take = min(remaining, available)

            handle = self.file_handles[index]
            handle.seek(slice_start)
            data = handle.read(take)
            if len(data) != take:
                raise OSError(
                    f"Unexpected early EOF in segment {self.part_paths[index].name!r}."
                )

            buffer.write(data)
            cursor += take
            remaining -= take

        self.used_ranges.append((offset, length))
        return buffer.getvalue()
