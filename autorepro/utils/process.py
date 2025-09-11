"""
Process execution utilities to eliminate duplicate subprocess patterns.

This module provides consistent subprocess execution with error handling, replacing
duplicate patterns found across the AutoRepro codebase.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SubprocessConfig:
    """Configuration for subprocess execution."""

    cmd: str | list[str]
    cwd: str | Path | None = None
    env: dict[str, str] | None = None
    timeout: int | None = None
    capture_output: bool = True
    text: bool = True
    check: bool = False


class ProcessResult:
    """Result of a process execution."""

    def __init__(self, exit_code: int, stdout: str, stderr: str, cmd: list[str]):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.cmd = cmd

    @property
    def success(self) -> bool:
        """True if process exited successfully (exit code 0)."""
        return self.exit_code == 0

    @property
    def cmd_str(self) -> str:
        """Command as a string for logging/display."""
        return " ".join(self.cmd)


class ProcessRunner:
    """Centralized process execution with consistent error handling."""

    @staticmethod
    def run_with_capture(
        cmd: str | list[str],
        cwd: str | Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        check: bool = False,
    ) -> ProcessResult:
        """
        Run command with output capture and consistent error handling.

        Args:
            cmd: Command to run (string or list of strings)
            cwd: Working directory for command execution
            env: Environment variables (merged with current env if provided)
            timeout: Timeout in seconds (None for no timeout)
            check: If True, raise exception on non-zero exit code

        Returns:
            ProcessResult with exit code, stdout, stderr

        Raises:
            subprocess.CalledProcessError: If check=True and command fails
            subprocess.TimeoutExpired: If command times out
            FileNotFoundError: If command executable is not found
            OSError: If command cannot be executed
        """
        # Convert string command to list
        if isinstance(cmd, str):
            cmd_list = cmd.split()
        else:
            cmd_list = list(cmd)

        # Convert path objects to strings
        if cwd is not None:
            cwd = str(cwd)

        try:
            result = subprocess.run(
                cmd_list,
                cwd=cwd,
                env=env,
                timeout=timeout,
                capture_output=True,
                text=True,
                check=check,
            )

            return ProcessResult(
                exit_code=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                cmd=cmd_list,
            )

        except subprocess.TimeoutExpired as e:
            stdout_str = ""
            if e.stdout:
                stdout_str = (
                    e.stdout.decode("utf-8")
                    if isinstance(e.stdout, bytes)
                    else e.stdout
                )
            return ProcessResult(
                exit_code=124,  # Standard timeout exit code
                stdout=stdout_str,
                stderr=f"Command timed out after {timeout} seconds",
                cmd=cmd_list,
            )
        except FileNotFoundError:
            return ProcessResult(
                exit_code=127,  # Standard "command not found" exit code
                stdout="",
                stderr=f"Command not found: {cmd_list[0]}",
                cmd=cmd_list,
            )
        except OSError as e:
            return ProcessResult(
                exit_code=1,
                stdout="",
                stderr=f"Failed to execute command: {e}",
                cmd=cmd_list,
            )

    @staticmethod
    def run_git_command(
        git_args: list[str], cwd: str | Path | None = None, check: bool = True
    ) -> ProcessResult:
        """
        Run git command with consistent error handling.

        Args:
            git_args: Git command arguments (without 'git' prefix)
            cwd: Working directory for git command
            check: If True, raise exception on non-zero exit code

        Returns:
            ProcessResult with git command output

        Raises:
            subprocess.CalledProcessError: If check=True and git command fails
        """
        cmd = ["git"] + git_args
        return ProcessRunner.run_with_capture(cmd, cwd=cwd, check=check)

    @staticmethod
    def run_gh_command(
        gh_args: list[str],
        cwd: str | Path | None = None,
        check: bool = True,
        gh_path: str = "gh",
    ) -> ProcessResult:
        """
        Run GitHub CLI command with consistent error handling.

        Args:
            gh_args: GitHub CLI command arguments (without 'gh' prefix)
            cwd: Working directory for gh command
            check: If True, raise exception on non-zero exit code
            gh_path: Path to gh executable (default: "gh")

        Returns:
            ProcessResult with gh command output

        Raises:
            subprocess.CalledProcessError: If check=True and gh command fails
        """
        cmd = [gh_path] + gh_args
        return ProcessRunner.run_with_capture(cmd, cwd=cwd, check=check)

    @staticmethod
    def run_python_command(
        python_args: list[str],
        cwd: str | Path | None = None,
        python_executable: str = "python",
        env: dict[str, str] | None = None,
        timeout: int | None = None,
    ) -> ProcessResult:
        """
        Run Python command with consistent error handling.

        Args:
            python_args: Python command arguments (without python prefix)
            cwd: Working directory for python command
            python_executable: Python executable name/path (default: "python")
            env: Additional environment variables
            timeout: Timeout in seconds

        Returns:
            ProcessResult with python command output
        """
        cmd = [python_executable] + python_args
        return ProcessRunner.run_with_capture(cmd, cwd=cwd, env=env, timeout=timeout)


def safe_subprocess_run(config: SubprocessConfig) -> subprocess.CompletedProcess:
    """
    Safe subprocess.run wrapper that handles common error cases.

    This is a drop-in replacement for subprocess.run with better error handling.
    Use ProcessRunner.run_with_capture for more structured results.

    Args:
        config: SubprocessConfig object containing all execution options

    Returns:
        subprocess.CompletedProcess result

    Raises:
        subprocess.CalledProcessError: If check=True and command fails
        subprocess.TimeoutExpired: If command times out
        FileNotFoundError: If command is not found
        OSError: If command cannot be executed
    """
    # Convert string command to list if needed
    cmd = config.cmd
    if isinstance(cmd, str):
        cmd = cmd.split()

    # Convert path to string if needed
    cwd = config.cwd
    if cwd is not None:
        cwd = str(cwd)

    return subprocess.run(
        cmd,
        cwd=cwd,
        env=config.env,
        timeout=config.timeout,
        capture_output=config.capture_output,
        text=config.text,
        check=config.check,
    )
