"""
File Import Component for collecting, validating, and filtering image files.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Iterable, Sequence

logger = logging.getLogger(__name__)

SUPPORTED_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".jpe",
    ".webp",
    ".bmp",
    ".tiff",
    ".tif",
}


class FileImportComponent:
    """
    Component responsible for importing, discovering, and validating image files.

    Attributes:
        _file_list (list[str]): Private storage for validated image file paths.
    """

    def __init__(self, allowed_extensions: set[str] | None = None) -> None:
        self._file_list: list[str] = []
        self._allowed_extensions: set[str] = (
            {ext.lower() for ext in allowed_extensions}
            if allowed_extensions is not None
            else SUPPORTED_IMAGE_EXTENSIONS
        )

    def _resolve_input(self, entry: str | Path) -> list[str]:
        """Resolve an entry (file or folder) into individual validated file path strings."""
        path = Path(entry).resolve()
        if not path.exists():
            logger.warning(f"FileImportComponent: Path does not exist and will be ignored: {path}")
            return []

        if path.is_file():
            if path.suffix.lower() in self._allowed_extensions:
                return [str(path)]
            logger.warning(
                f"FileImportComponent: File extension '{path.suffix}' not supported. Allowed: {self._allowed_extensions}"
            )
            return []

        if path.is_dir():
            # Scan directory for supported files, sorted for deterministic processing
            discovered: list[str] = []
            for child in sorted(path.iterdir()):
                if child.is_file() and child.suffix.lower() in self._allowed_extensions:
                    discovered.append(str(child.resolve()))
            return discovered

        return []

    def setter(self, file_list: str | Path | Sequence[str | Path]) -> None:
        """
        Accept all files in file_list into private _file_list.
        Supports:
        - A single file path (str or Path)
        - A directory path (str or Path)
        - A list or sequence of paths
        """
        collected: list[str] = []

        if isinstance(file_list, (str, Path)):
            entries: Iterable[str | Path] = [file_list]
        elif isinstance(file_list, Sequence):
            entries = file_list
        else:
            entries = list(file_list)

        for entry in entries:
            collected.extend(self._resolve_input(entry))

        # Deduplicate while preserving sequence order
        seen = set()
        deduped: list[str] = []
        for f in collected:
            if f not in seen:
                seen.add(f)
                deduped.append(f)

        self._file_list = deduped

    def getter(self) -> list[str]:
        """
        If private _file_list is not null, return the latest file list.
        Returns a fresh list copy.
        """
        if self._file_list:
            return list(self._file_list)
        return []

    def clear(self) -> None:
        """Clear current stored file list."""
        self._file_list = []

