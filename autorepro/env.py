"""Environment and devcontainer management for AutoRepro."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from shutil import which
from typing import Any

from .config import config


def python_bin() -> str:
    """
    Return path to Python executable using priority-based detection.

    Searches for Python executable in the following order:
    1. PYTHON_BIN environment variable (if exists and valid)
    2. VIRTUAL_ENV/bin/python (or Scripts/python on Windows)
    3. sys.executable (current Python interpreter)
    4. which("python3") then which("python") from PATH

    Returns:
        str: Path to Python executable, or "python" as fallback
    """
    env_bin = os.environ.get("PYTHON_BIN")
    if env_bin and Path(env_bin).exists():
        return env_bin
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        cand = Path(venv) / ("Scripts" if os.name == "nt" else "bin") / "python"
        if cand.exists():
            return str(cand)
    if Path(sys.executable).exists():
        return sys.executable
    for name in config.executables.python_names:
        path = which(name)
        if path:
            return path
    return "python"


class DevcontainerExistsError(Exception):
    """Raised when devcontainer file already exists and force=False."""

    def __init__(self, path: Path):
        """
        Initialize DevcontainerExistsError.

        Args:
            path (Path): The path where devcontainer file already exists
        """
        self.path = path
        super().__init__(f"File already exists: {path}")


class DevcontainerMisuseError(Exception):
    """Raised when arguments are invalid (e.g., output path is a directory)."""

    def __init__(self, message: str):
        """
        Initialize DevcontainerMisuseError.

        Args:
            message (str): Error message describing the misuse
        """
        self.message = message
        super().__init__(message)


def default_devcontainer() -> dict[str, str | dict[str, dict[str, str]]]:
    """Return the default devcontainer configuration."""
    return {
        "name": "autorepro-dev",
        "features": {
            "ghcr.io/devcontainers/features/python:1": {"version": "3.11"},
            "ghcr.io/devcontainers/features/node:1": {"version": "20"},
            "ghcr.io/devcontainers/features/go:1": {"version": "1.22"},
        },
        "postCreateCommand": (
            "python -m venv .venv && source .venv/bin/activate && python -m pip install -e ."
        ),
    }


def _shorten_value(value_str: str, max_length: int | None = None) -> str:
    """
    Shorten a JSON string representation if it's too long.
    Show first/last portions with length indicator for long values.
    """
    if max_length is None:
        max_length = config.limits.max_display_length

    if len(value_str) <= max_length:
        return value_str

    # For very long values, show first/last 40 characters with ellipsis and length
    first_part = value_str[:40]
    last_part = value_str[-40:]
    return f"{first_part}...{last_part} (length: {len(value_str)})"


def json_diff(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """
    Return a list of human-readable change lines comparing `old` vs `new`,
    using dot-paths (e.g., features.go.version) and action prefixes:
      + path: <new>
      - path: <old>
      ~ path: <old> -> <new>
    Rules:
    - Walk nested dicts recursively (ignore key ordering).
    - For scalars, consider changed if values differ.
    - For lists/other non-dict types: treat as scalar; if unequal, emit `~`.
    - Use JSON-like rendering for values: json.dumps(value, ensure_ascii=False).
    - Paths use dot-notation; do not include indices (lists treated as scalar values).
    - Long values are shortened for display with first/last 40 chars and length indicator.
    - Return lines **sorted by path** for deterministic output.
    """

    def _walk_diff(
        old_dict: dict[str, Any], new_dict: dict[str, Any], prefix: str = ""
    ) -> list[str]:
        """Recursively walk through dictionaries to find differences."""
        changes = []

        # Get all keys from both dictionaries
        all_keys = set(old_dict.keys()) | set(new_dict.keys())

        for key in all_keys:
            # Quote keys that contain dots or other special characters
            safe_key = f'["{key}"]' if "." in str(key) else str(key)
            current_path = f"{prefix}.{safe_key}" if prefix else safe_key

            if key not in old_dict:
                # Key added
                new_val = json.dumps(new_dict[key], ensure_ascii=False)
                new_val = _shorten_value(new_val)
                changes.append(f"+ {current_path}: {new_val}")
            elif key not in new_dict:
                # Key removed
                old_val = json.dumps(old_dict[key], ensure_ascii=False)
                old_val = _shorten_value(old_val)
                changes.append(f"- {current_path}: {old_val}")
            else:
                old_val = old_dict[key]
                new_val = new_dict[key]

                # If both are dictionaries, recurse
                if isinstance(old_val, dict) and isinstance(new_val, dict):
                    changes.extend(_walk_diff(old_val, new_val, current_path))
                # Otherwise, treat as scalars and compare
                elif old_val != new_val:
                    old_json = json.dumps(old_val, ensure_ascii=False)
                    new_json = json.dumps(new_val, ensure_ascii=False)
                    old_json = _shorten_value(old_json)
                    new_json = _shorten_value(new_json)
                    changes.append(f"~ {current_path}: {old_json} -> {new_json}")

        return changes

    changes = _walk_diff(old, new)
    return sorted(changes)  # Sort by path for deterministic output


def write_devcontainer(
    content: dict[str, str | dict[str, dict[str, str]]], force: bool = False, out: str | None = None
) -> tuple[Path, list[str] | None]:
    """
    Write devcontainer configuration to file with atomic and idempotent behavior.

    Args:
        content: Devcontainer configuration dictionary
        force: If True, overwrite existing file
        out: Custom output path (default: .devcontainer/devcontainer.json)

    Returns:
        tuple[Path, list[str] | None]: The path where the file was written and diff information.
        - If file was newly created: (path, None)
        - If file existed and force is False: (path, None) - caller handles "already exists"
        - If file existed and force is True: (path, diff_lines) - diff_lines may be empty

    Raises:
        DevcontainerExistsError: File exists and force=False
        DevcontainerMisuseError: Invalid arguments (e.g., out points to directory)
        OSError: I/O or permission errors
    """
    # Determine output path
    output_path = (
        Path(config.paths.devcontainer_dir) / config.paths.devcontainer_file
        if out is None
        else Path(out)
    )

    # Validate output path
    try:
        # Normalize path and check if it's valid
        output_path = output_path.resolve()
    except (OSError, ValueError) as e:
        raise DevcontainerMisuseError(f"Invalid output path '{out}': {e}") from e

    # Check if output path is a directory (handle permission errors separately)
    try:
        if output_path.exists() and output_path.is_dir():
            raise DevcontainerMisuseError(f"Output path is a directory: {output_path}")
    except (OSError, PermissionError) as e:
        if not isinstance(e, DevcontainerMisuseError):
            raise OSError(f"Permission denied: {output_path.parent}") from e
        raise

    # Check if parent directory can be created
    try:
        parent_dir = output_path.parent
        if not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as e:
        raise OSError(f"Cannot create parent directory: {parent_dir}") from e

    # Check if file exists and handle idempotent behavior
    try:
        file_exists = output_path.exists()
    except (OSError, PermissionError) as e:
        raise OSError(f"Permission denied: {output_path.parent}") from e

    diff_lines = None

    if file_exists:
        if not force:
            raise DevcontainerExistsError(output_path)

        # Check write permissions on existing file
        if not os.access(output_path, os.W_OK):
            raise PermissionError(f"Permission denied: {output_path}")

        # Read existing file and compute diff
        try:
            with open(output_path, encoding="utf-8") as f:
                old_content = json.load(f)
            diff_lines = json_diff(old_content, content)
        except (OSError, json.JSONDecodeError):
            # If we can't read the old file as JSON, treat it as a complete replacement
            diff_lines = []
    else:
        # Check write permissions on parent directory for new file
        if not os.access(output_path.parent, os.W_OK):
            raise PermissionError(f"Permission denied: {output_path.parent}")

    # Create content with proper formatting
    json_content = json.dumps(content, indent=2, sort_keys=True) + "\n"

    # Check if content is actually different before writing
    if file_exists:
        try:
            with open(output_path, encoding="utf-8") as f:
                existing_content = f.read()
            if existing_content == json_content:
                # No actual changes, return without writing to preserve mtime
                return output_path, diff_lines
        except (OSError, UnicodeDecodeError):
            # If we can't read the existing file, proceed with write
            pass

    # Write file atomically
    try:
        # Write to temporary file first, then move (atomic operation)
        temp_path = output_path.with_suffix(output_path.suffix + config.paths.temp_file_suffix)

        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(json_content)

            # Atomic move
            temp_path.rename(output_path)

            return output_path, diff_lines

        except Exception:
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            raise

    except (OSError, PermissionError) as e:
        raise OSError(f"Failed to write file: {e}") from e
