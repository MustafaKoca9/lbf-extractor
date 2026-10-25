"""Output path confinement and safe publication of completed files."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .common import SecurityError


class PathMixin:
    def get_safe_destination(self, virtual_path: str) -> Path:
        """Return a canonical destination confined to output_dir.

        Parent traversal is rejected instead of rewritten so suspicious metadata
        cannot silently map to an unexpected output filename.
        """
        if not isinstance(virtual_path, str):
            raise SecurityError(
                f"Output path must be text, got {type(virtual_path).__name__}."
            )

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
        except (OSError, RuntimeError, ValueError) as exc:
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

        if not self.overwrite and os.path.lexists(candidate):
            return self._next_available_path(candidate)
        return candidate

    @staticmethod
    def _next_available_path(path: Path) -> Path:
        stem, suffix = path.stem, path.suffix
        counter = 1
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        while os.path.lexists(candidate):
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
                # Same-directory linking is atomic and cannot overwrite a path
                # that appeared after get_safe_destination() was called.
                os.link(temporary_path, candidate)
            except FileExistsError:
                counter += 1
                continue
            try:
                os.unlink(temporary_path)
            except OSError:
                # The output has already been published safely. The caller's
                # cleanup path will make another best-effort attempt.
                pass
            return candidate

    def write_text_safely(self, virtual_path: str, contents: str) -> Path:
        """Write UTF-8 text to a temporary file and publish it atomically."""
        destination = self.get_safe_destination(virtual_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                prefix=f".{destination.name}.",
                suffix=".part",
                dir=str(destination.parent),
                delete=False,
            ) as stream:
                temporary_path = Path(stream.name)
                stream.write(contents)
            return self.publish_temp_file(temporary_path, destination)
        finally:
            if temporary_path is not None:
                try:
                    temporary_path.unlink(missing_ok=True)
                except OSError:
                    pass
