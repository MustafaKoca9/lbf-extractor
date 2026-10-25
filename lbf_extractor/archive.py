from pathlib import Path
from .common import CorruptedArchiveError
class ArchiveMixin:
    def _load_archive_segments(self) -> None:
        """Discover and open .lbf plus .lbf0/.lbf1/… slices in logical order.

        Default order (LG convention): .lbf0, .lbf1, …, .lbf (primary last).
        Pass ``split_lbf_first=True`` for the opposite convention.
        """
        slices: List[Path] = []
        idx = 0
        while True:
            sliced = self.archive_path.parent / f"{self.archive_path.name}{idx}"
            if sliced.is_file():
                slices.append(sliced)
                idx += 1
            else:
                break

        paths = (
            [self.archive_path] + slices
            if self.split_lbf_first
            else slices + [self.archive_path]
        )

        cumulative = 0
        try:
            for path in paths:
                fh = open(path, "rb")
                fh.seek(0, os.SEEK_END)
                cumulative += fh.tell()
                self.file_handles.append(fh)
                self.part_boundaries.append(cumulative)
        except OSError:
            self._cleanup()
            raise

        self.part_paths = paths
        self.total_size = cumulative

    # ---- logical reads ----------------------------------------------------

    def _find_slice_index(self, offset: int) -> int:
        if offset < 0 or offset >= self.total_size:
            raise IndexError(
                f"Logical offset out of boundary: {offset:,} / {self.total_size:,}"
            )
        for i, boundary in enumerate(self.part_boundaries):
            if offset < boundary:
                return i
        raise RuntimeError(f"Unresolvable slice index for offset {offset}")

    def read_bytes(self, offset: int, length: int) -> bytes:
        """Read a byte buffer spanning any number of segment boundaries."""
        if length < 0 or offset < 0 or offset + length > self.total_size:
            raise ValueError(
                f"Illegal boundary read requested: "
                f"offset={offset:,}, length={length:,}"
            )

        buf = io.BytesIO()
        remaining = length
        cursor = offset
        while remaining > 0:
            idx = self._find_slice_index(cursor)
            slice_start = (
                cursor if idx == 0 else cursor - self.part_boundaries[idx - 1]
            )
            available = self.part_boundaries[idx] - cursor
            take = min(remaining, available)

            self.file_handles[idx].seek(slice_start)
            data = self.file_handles[idx].read(take)
            if len(data) != take:
                raise OSError("Unexpected early EOF while reading segment slice.")

            buf.write(data)
            cursor += take
            remaining -= take

        self.used_ranges.append((offset, length))
        return buf.getvalue()

    # ---- destination path safety -----------------------------------------
