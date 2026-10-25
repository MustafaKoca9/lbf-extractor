"""Simple output-directory and file-writing helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Union


class OutputManager:
    """Build output paths and write complete files directly."""

    def __init__(self, output_dir: Union[str, Path] = "./export", overwrite: bool = False) -> None:
        self.output_dir = Path(output_dir).expanduser().resolve()
        self.overwrite = overwrite

    def prepare(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def is_empty(self) -> bool:
        self.prepare()
        return next(self.output_dir.iterdir(), None) is None

    def get_destination(self, relative_path: str) -> Path:
        destination = self.output_dir / Path(relative_path)
        if self.overwrite or not destination.exists():
            return destination
        stem, suffix = destination.stem, destination.suffix
        counter = 1
        while True:
            candidate = destination.with_name(f"{stem}_{counter}{suffix}")
            if not candidate.exists():
                return candidate
            counter += 1

    def write_bytes(self, relative_path: str, content: bytes) -> Path:
        destination = self.get_destination(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return destination

    def write_text(self, relative_path: str, content: str) -> Path:
        destination = self.get_destination(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")
        return destination
