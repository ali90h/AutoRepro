"""Utility functions for tests."""

import os
import subprocess
import sys


def get_project_root():
    """Get the project root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_autorepro_subprocess(args, cwd=None, **kwargs):
    """
    Helper to run autorepro CLI via subprocess with proper module resolution.

    Args:
        args: List of arguments to pass to autorepro CLI
        cwd: Working directory for the command
        **kwargs: Additional arguments for subprocess.run

    Returns:
        subprocess.CompletedProcess with returncode, stdout, stderr
    """
    project_root = get_project_root()
    args_str = ", ".join(f"'{arg}'" for arg in args)
    cmd = [
        sys.executable,
        "-c",
        f"import sys; sys.path.insert(0, '{project_root}'); from autorepro.cli import main; "
        f"sys.exit(main([{args_str}]))",
    ]

    # Set default values
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("timeout", 30)

    return subprocess.run(cmd, cwd=cwd, **kwargs)
