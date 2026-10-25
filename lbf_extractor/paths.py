import os
from pathlib import Path
from .common import SecurityError
class PathMixin:
    def get_safe_destination(self, virtual_path: str) -> Path:
        """Sanitize, confine to output_dir, then de-duplicate.

        Raises:
            SecurityError: if a canonical path check escapes the output root.
        """
        sanitized = virtual_path.replace("\\", "/").strip("/")
        tokens = [t for t in sanitized.split("/") if t not in ("", ".")]

        if any(t == ".." for t in tokens):
            self.logger.warning(
                "Path traversal sequence '..' blocked in: %r", virtual_path
            )
            tokens = [t for t in tokens if t != ".."]

        if not tokens:
            tokens = ["unnamed_item"]

        candidate = (self.output_dir / Path(*tokens)).resolve()

        try:
            common = os.path.commonpath(
                [str(self.output_dir), str(candidate)]
            )
        except ValueError as exc:
            raise SecurityError(
                f"Cross-drive path traversal blocked: {virtual_path!r} ({exc})"
            ) from exc

        if common != str(self.output_dir):
            raise SecurityError(
                f"Directory traversal exploit detected: {virtual_path!r} "
                f"resolves to {candidate}"
            )

        if not self.overwrite and candidate.exists():
            original = candidate
            stem, suffix = original.stem, original.suffix
            counter = 1
            while candidate.exists():
                candidate = original.with_name(f"{stem}_{counter}{suffix}")
                counter += 1

        return candidate

    # ---- crypto / header --------------------------------------------------
