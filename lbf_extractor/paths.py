"""Output destination policy and atomic file publication."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Union

from .common import SecurityError


class OutputManager:
    """Confine output paths and publish completed files without partial overwrite."""

    def __init__(
        self,
        output_dir: Union[str, Path] = "./export",
        overwrite: bool = False,
    ) -> None:
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.overwrite = overwrite

    def prepare(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def is_empty(self) -> bool:
        self.prepare()
        return next(self.output_dir.iterdir(), None) is None

    def get_safe_destination(self, virtual_path: str) -> Path:
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
        if self.overwrite:
            os.replace(temporary_path, destination)
            return destination

        counter = 0
        while True:
            candidate = (
                destination if counter == 0
                else destination.with_name(
                    f"{destination.stem}_{counter}{destination.suffix}"
                )
            )
            try:
                # Same-directory linking is atomic and never replaces an existing file.
                os.link(temporary_path, candidate)
            except FileExistsError:
                counter += 1
                continue
            try:
                os.unlink(temporary_path)
            except OSError:
                pass
            return candidate

    def write_text_safely(self, virtual_path: str, contents: str) -> Path:
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
