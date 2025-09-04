#!/usr/bin/env python3
"""Script to apply consistent formatting fixes for CI compliance."""

import subprocess
from pathlib import Path

# Files that need formatting fixes based on CI error
FILES_TO_FORMAT = [
    "test_env_and_node.py",
    "tests/test_file_path_resolution.py",
    "tests/test_focused_implementation.py",
    "tests/test_init.py",
    "tests/test_plan_strict_mode.py",
    "tests/test_repo_stability.py",
    "tests/test_plan_core.py",
    "tests/test_plan_cli.py",
]


def run_formatters():
    """Run black and ruff format on the specified files."""
    for file in FILES_TO_FORMAT:
        if Path(file).exists():
            print(f"Formatting {file}...")
            subprocess.run(["python", "-m", "black", file], check=True)
            subprocess.run(["ruff", "format", file], check=True)
        else:
            print(f"Warning: {file} not found")


if __name__ == "__main__":
    run_formatters()
    print("Formatting complete!")
