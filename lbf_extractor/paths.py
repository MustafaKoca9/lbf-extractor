"""Output path confinement and safe publication of completed files."""
from __future__ import annotations

import os
from pathlib import Path

from .common import SecurityError


class PathMixin:
    def get_safe_destination(self, virtual_path: str) -> Path:
        """Return a canonical destination confined to output_dir.

        Parent traversal is rejected instead of rewritten so suspicious metadata
        cannot silently map to an unexpected output filename.
        """
        if not isinstance(virtual_path, str):
            raise SecurityError(f"Output path must be text, got {type(virtual_path).__name__}.")

        sanitized = virtual_path.replace("\\", "/").strip("/")
        tokens = [token for token in sanitized.split("/") if token not in ("", ".")]

        if any(token == ".." for token in tokens):
            raise SecurityError(f"Parent-directory traversal blocked: {virtual_path!r}")
        if not tokens:
            tokens = ["unnamed_item"]

        try:
            root = self.output_dir.resolve()
            candidate = (root / Path(*tokens)).resolve()
            common = Path(os.path.commonpath([str(root), str(candidate)]))
        except (OSError, ValueError) as exc:
            raise SecurityError(
                f"Could not safely resolve output path {virtual_path!r}: {exc}"
            ) from exc

        if common != root:
            raise SecurityError(
                f"Destination escapes the output directory: {virtual_path!r}"
            )

        if candidate.is_dir():
            if not self.overwrite:
                return self._next_available_path(candidate)
            raise SecurityError(f"Refusing to overwrite a directory: {candidate}")

        if not self.overwrite and candidate.exists():
            return self._next_available_path(candidate)
        return candidate

    @staticmethod
    def _next_available_path(path: Path) -> Path:
        stem, suffix = path.stem, path.suffix
        counter = 1
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        while candidate.exists():
            counter += 1
            candidate = path.with_name(f"{stem}_{counter}{suffix}")
        return candidate

    def publish_temp_file(self, temporary_path: Path, destination: Path) -> Path:
        """Publish a fully written temporary file without clobbering by default."""
        if self.overwrite:
            os.replace(temporary_path, destination)
            return destination

        base = destination
        counter = 0
        while True:
            candidate = (
                base if counter == 0
                else base.with_name(f"{base.stem}_{counter}{base.suffix}")
            )
            try:
                # The temporary file lives in the same directory, so the link is
                # atomic and cannot replace a destination that appeared meanwhile.
                os.link(temporary_path, candidate)
            except FileExistsError:
                counter += 1
                continue
            os.unlink(temporary_path)
            return candidate
