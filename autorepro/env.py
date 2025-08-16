"""Environment and devcontainer management for AutoRepro."""

import json
import os
from pathlib import Path


class DevcontainerExistsError(Exception):
    """Raised when devcontainer file already exists and force=False."""

    def __init__(self, path: Path):
        self.path = path
        super().__init__(f"File already exists: {path}")


class DevcontainerMisuseError(Exception):
    """Raised when arguments are invalid (e.g., output path is a directory)."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def default_devcontainer() -> dict:
    """Return the default devcontainer configuration."""
    return {
        "name": "autorepro-dev",
        "features": {
            "ghcr.io/devcontainers/features/python:1": {"version": "3.11"},
            "ghcr.io/devcontainers/features/node:1": {"version": "20"},
            "ghcr.io/devcontainers/features/go:1": {"version": "1.22"},
        },
        "postCreateCommand": (
            "python -m venv .venv && source .venv/bin/activate && pip install -e ."
        ),
    }


def write_devcontainer(content: dict, force: bool = False, out: str | None = None) -> Path:
    """
    Write devcontainer configuration to file with atomic and idempotent behavior.

    Args:
        content: Devcontainer configuration dictionary
        force: If True, overwrite existing file
        out: Custom output path (default: .devcontainer/devcontainer.json)

    Returns:
        Path: The path where the file was written

    Raises:
        DevcontainerExistsError: File exists and force=False
        DevcontainerMisuseError: Invalid arguments (e.g., out points to directory)
        OSError: I/O or permission errors
    """
    # Determine output path
    if out is None:
        output_path = Path(".devcontainer") / "devcontainer.json"
    else:
        output_path = Path(out)

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

    if file_exists:
        if not force:
            raise DevcontainerExistsError(output_path)

        # Check write permissions on existing file
        if not os.access(output_path, os.W_OK):
            raise PermissionError(f"Permission denied: {output_path}")
    else:
        # Check write permissions on parent directory for new file
        if not os.access(output_path.parent, os.W_OK):
            raise PermissionError(f"Permission denied: {output_path.parent}")

    # Write file atomically
    try:
        # Create content with proper formatting
        json_content = json.dumps(content, indent=2, sort_keys=True) + "\n"

        # Write to temporary file first, then move (atomic operation)
        temp_path = output_path.with_suffix(output_path.suffix + ".tmp")

        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(json_content)

            # Atomic move
            temp_path.rename(output_path)

            return output_path

        except Exception:
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            raise

    except (OSError, PermissionError) as e:
        raise OSError(f"Failed to write file: {e}") from e
