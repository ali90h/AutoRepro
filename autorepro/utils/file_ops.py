"""
File operations utilities to eliminate duplicate I/O patterns.

This module provides consistent file operations with error handling,
replacing duplicate patterns found across the AutoRepro codebase.
"""

import json
import tempfile
from pathlib import Path
from typing import Any


class FileOperations:
    """Centralized file operations with consistent error handling."""

    @staticmethod
    def ensure_directory(path: Path) -> None:
        """Ensure directory exists, create with parents if needed.

        Args:
            path: Directory path to ensure exists

        Raises:
            OSError: If directory cannot be created due to permissions
        """
        try:
            path.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            raise OSError(f"Cannot create directory: {path}") from e

    @staticmethod
    def atomic_write(path: Path, content: str, encoding: str = "utf-8") -> None:
        """Atomic file write using temp file + rename pattern.

        Args:
            path: Target file path
            content: Content to write
            encoding: File encoding (default: utf-8)

        Raises:
            OSError: If file cannot be written due to permissions or I/O error
        """
        try:
            # Ensure parent directory exists
            FileOperations.ensure_directory(path.parent)

            # Write to temporary file first
            temp_path = path.with_suffix(path.suffix + ".tmp")
            with open(temp_path, "w", encoding=encoding) as f:
                f.write(content)

            # Atomic rename
            temp_path.rename(path)

        except (OSError, PermissionError) as e:
            # Clean up temp file if it exists
            temp_path = path.with_suffix(path.suffix + ".tmp")
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError:
                    pass  # Best effort cleanup
            raise OSError(f"Failed to write file: {path}") from e

    @staticmethod
    def safe_read_text(path: Path, encoding: str = "utf-8", default: str | None = None) -> str:
        """Read text file with fallback on error.

        Args:
            path: File path to read
            encoding: File encoding (default: utf-8)
            default: Default value if file cannot be read (default: None raises error)

        Returns:
            File content as string

        Raises:
            OSError: If file cannot be read and no default provided
        """
        try:
            return path.read_text(encoding=encoding)
        except (FileNotFoundError, OSError, UnicodeDecodeError) as e:
            if default is not None:
                return default
            raise OSError(f"Failed to read file: {path}") from e

    @staticmethod
    def safe_read_json(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
        """Read JSON file with fallback on error.

        Args:
            path: JSON file path to read
            default: Default value if file cannot be read or parsed

        Returns:
            Parsed JSON content as dictionary

        Raises:
            OSError: If file cannot be read and no default provided
            json.JSONDecodeError: If JSON is invalid and no default provided
        """
        try:
            content = FileOperations.safe_read_text(path)
            return json.loads(content)
        except (OSError, json.JSONDecodeError) as e:
            if default is not None:
                return default
            raise e

    @staticmethod
    def atomic_write_json(
        path: Path,
        data: dict[str, Any],
        indent: int = 2,
        sort_keys: bool = True,
        ensure_ascii: bool = False,
    ) -> None:
        """Atomic JSON file write with consistent formatting.

        Args:
            path: Target JSON file path
            data: Data to serialize as JSON
            indent: JSON indentation (default: 2)
            sort_keys: Whether to sort keys (default: True)
            ensure_ascii: Whether to ensure ASCII encoding (default: False)

        Raises:
            OSError: If file cannot be written
        """
        try:
            json_content = json.dumps(
                data, indent=indent, sort_keys=sort_keys, ensure_ascii=ensure_ascii
            )
            # Ensure trailing newline for consistent formatting
            if not json_content.endswith("\n"):
                json_content += "\n"

            FileOperations.atomic_write(path, json_content)

        except (TypeError, ValueError) as e:
            raise OSError(f"Failed to serialize JSON data: {e}") from e


def create_temp_file(content: str, suffix: str = "", encoding: str = "utf-8") -> Path:
    """Create a temporary file with content and return the path.

    Args:
        content: Content to write to temp file
        suffix: File suffix (default: empty)
        encoding: File encoding (default: utf-8)

    Returns:
        Path to the created temporary file

    Note:
        Caller is responsible for cleaning up the temporary file.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, encoding=encoding, delete=False) as f:
        f.write(content)
        return Path(f.name)
