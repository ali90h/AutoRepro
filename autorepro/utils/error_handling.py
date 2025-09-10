"""
Standardized error handling utilities for subprocess and file operations.

This module provides consistent error handling patterns to replace scattered
exception handling across the AutoRepro codebase, particularly for subprocess
execution and file operations.
"""

import contextlib
import logging
import subprocess
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path

from .file_ops import FileOperations
from .process import SubprocessConfig


@dataclass
class ErrorContext:
    """Context information for error reporting."""

    operation: str | None = None
    path: Path | str | None = None
    log_operations: bool = False


@dataclass
class SubprocessDetails:
    """Container for subprocess execution details."""

    cmd: str | list[str]
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None

    @property
    def cmd_str(self) -> str:
        """Command as a string for display."""
        return self.cmd if isinstance(self.cmd, str) else " ".join(self.cmd)


class AutoReproError(Exception):
    """Base exception class for AutoRepro operations."""

    def __init__(self, message: str, operation: str | None = None, cause: Exception | None = None):
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.cause = cause


class SubprocessError(AutoReproError):
    """Standardized exception for subprocess execution errors."""

    def __init__(
        self,
        message: str,
        details: SubprocessDetails,
        *,
        operation: str | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message, operation, cause)
        self.details = details
        # Maintain backward compatibility by exposing details as direct attributes
        self.cmd = details.cmd_str
        self.exit_code = details.exit_code
        self.stdout = details.stdout
        self.stderr = details.stderr


class FileOperationError(AutoReproError):
    """Standardized exception for file operation errors."""

    def __init__(
        self,
        message: str,
        path: Path | str | None = None,
        operation: str | None = None,
        cause: Exception | None = None,
    ):
        super().__init__(message, operation, cause)
        self.path = Path(path) if path else None


def safe_subprocess_run(
    cmd: str | list[str],
    *,
    config: SubprocessConfig | None = None,
    operation: str | None = None,
    log_command: bool = False,
) -> subprocess.CompletedProcess:
    """Safe subprocess.run wrapper with consistent error formatting and logging.

    This is a drop-in replacement for subprocess.run with standardized error handling,
    consistent logging, and better error messages.

    Args:
        cmd: Command to run (string or list of strings)
        config: SubprocessConfig object containing execution options, or None for defaults
        operation: Operation name for logging and error messages
        log_command: Whether to log the command being executed

    Returns:
        subprocess.CompletedProcess result

    Raises:
        SubprocessError: If command fails and check=True, or on execution errors
    """
    return _safe_subprocess_run_impl(cmd, config, operation, log_command)


def safe_subprocess_run_simple(
    cmd: str | list[str],
    *,
    run_config: SubprocessConfig | None = None,
    operation: str | None = None,
    log_command: bool = False,
    **subprocess_kwargs,
) -> subprocess.CompletedProcess:
    """Backward-compatible interface for safe_subprocess_run with individual parameters.

    Args:
        cmd: Command to run (string or list of strings)
        run_config: Optional SubprocessConfig object. If not provided, uses subprocess_kwargs
        operation: Operation name for logging and error messages
        log_command: Whether to log the command being executed
        **subprocess_kwargs: Individual subprocess parameters (cwd, env, timeout, etc.)

    Returns:
        subprocess.CompletedProcess result

    Raises:
        SubprocessError: If command fails and check=True, or on execution errors
    """
    if run_config is None:
        # Create config from individual kwargs for backward compatibility
        run_config = SubprocessConfig(
            cmd=cmd,
            cwd=subprocess_kwargs.get("cwd"),
            env=subprocess_kwargs.get("env"),
            timeout=subprocess_kwargs.get("timeout"),
            capture_output=subprocess_kwargs.get("capture_output", True),
            text=subprocess_kwargs.get("text", True),
            check=subprocess_kwargs.get("check", False),
        )
    else:
        run_config.cmd = cmd
    return _safe_subprocess_run_impl(cmd, run_config, operation, log_command)


def _safe_subprocess_run_impl(
    cmd: str | list[str],
    config: SubprocessConfig | None,
    operation: str | None,
    log_command: bool,
) -> subprocess.CompletedProcess:
    """Safe subprocess.run wrapper with consistent error formatting and logging.

    This is a drop-in replacement for subprocess.run with standardized error handling,
    consistent logging, and better error messages.

    Args:
        cmd: Command to run (string or list of strings)
        config: SubprocessConfig object containing execution options, or None for defaults
        operation: Operation name for logging and error messages
        log_command: Whether to log the command being executed

    Returns:
        subprocess.CompletedProcess result

    Raises:
        SubprocessError: If command fails and check=True, or on execution errors
    """
    logger = logging.getLogger("autorepro")

    # Use provided config or create default
    if config is None:
        config = SubprocessConfig(cmd=cmd)
    else:
        # Override command if provided explicitly
        config = SubprocessConfig(
            cmd=cmd,
            cwd=config.cwd,
            env=config.env,
            timeout=config.timeout,
            capture_output=config.capture_output,
            text=config.text,
            check=config.check,
        )

    # Format command for logging
    cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)
    operation_name = operation or "subprocess"

    if log_command:
        logger.debug(f"Running {operation_name}: {cmd_str}")

    try:
        result = subprocess.run(
            config.cmd if isinstance(config.cmd, list) else config.cmd.split(),
            cwd=str(config.cwd) if config.cwd else None,
            env=config.env,
            timeout=config.timeout,
            capture_output=config.capture_output,
            text=config.text,
            check=config.check,
        )

        if result.returncode != 0 and log_command:
            logger.warning(f"{operation_name} exited with code {result.returncode}: {cmd_str}")

        return result

    except subprocess.CalledProcessError as e:
        error_msg = f"{operation_name} failed with exit code {e.returncode}: {cmd_str}"
        logger.error(error_msg)
        details = SubprocessDetails(
            cmd=cmd,
            exit_code=e.returncode,
            stdout=e.stdout.decode("utf-8", errors="replace") if e.stdout else None,
            stderr=e.stderr.decode("utf-8", errors="replace") if e.stderr else None,
        )
        raise SubprocessError(
            message=error_msg,
            details=details,
            operation=operation_name,
            cause=e,
        ) from e
    except subprocess.TimeoutExpired as e:
        error_msg = f"{operation_name} timed out after {config.timeout}s: {cmd_str}"
        logger.error(error_msg)
        details = SubprocessDetails(
            cmd=cmd,
            exit_code=124,  # Standard timeout exit code
            stdout=e.stdout.decode("utf-8", errors="replace") if e.stdout else None,
            stderr=e.stderr.decode("utf-8", errors="replace") if e.stderr else None,
        )
        raise SubprocessError(
            message=error_msg,
            details=details,
            operation=operation_name,
            cause=e,
        ) from e
    except FileNotFoundError as e:
        error_msg = f"{operation_name} command not found: {cmd_str}"
        logger.error(error_msg)
        details = SubprocessDetails(
            cmd=cmd,
            exit_code=127,  # Standard "command not found" exit code
        )
        raise SubprocessError(
            message=error_msg,
            details=details,
            operation=operation_name,
            cause=e,
        ) from e
    except OSError as e:
        # In some sandboxed environments (e.g., macOS seatbelt), certain subprocess
        # executions can raise EPERM (Operation not permitted) instead of timing out.
        # If a timeout was requested, normalize this to a timeout to keep behavior
        # consistent and predictable for callers and tests.
        try:
            errno_val = getattr(e, "errno", None)
        except Exception:
            errno_val = None

        if config.timeout is not None and (errno_val == 1 or "not permitted" in str(e).lower()):
            te = subprocess.TimeoutExpired(
                cmd if isinstance(cmd, list) else (cmd.split() if isinstance(cmd, str) else cmd),
                config.timeout,
            )
            error_msg = f"{operation_name} timed out after {config.timeout}s: {cmd_str}"
            logger.error(error_msg)
            details = SubprocessDetails(
                cmd=cmd,
                exit_code=124,
            )
            raise SubprocessError(
                message=error_msg,
                details=details,
                operation=operation_name,
                cause=te,
            ) from e

        error_msg = f"{operation_name} execution failed: {e}"
        logger.error(error_msg)
        details = SubprocessDetails(
            cmd=cmd,
            exit_code=1,
        )
        raise SubprocessError(
            message=error_msg,
            details=details,
            operation=operation_name,
            cause=e,
        ) from e


@contextlib.contextmanager
def safe_file_operation(
    operation: str, path: Path | str | None = None, log_operations: bool = False
) -> Generator[None, None, None]:
    """Context manager for safe file operations with consistent error handling.

    Args:
        operation: Name of the file operation for logging and error messages
        path: File/directory path involved in the operation
        log_operations: Whether to log the start/completion of operations

    Yields:
        None

    Raises:
        FileOperationError: If any file operation error occurs within the context
    """
    logger = logging.getLogger("autorepro")
    path_str = str(path) if path else "unknown"

    if log_operations:
        logger.debug(f"Starting {operation}: {path_str}")

    try:
        yield
        if log_operations:
            logger.debug(f"Completed {operation}: {path_str}")
    except (OSError, PermissionError, FileNotFoundError, UnicodeDecodeError) as e:
        error_msg = f"{operation} failed for {path_str}: {e}"
        logger.error(error_msg)
        raise FileOperationError(message=error_msg, path=path, operation=operation, cause=e) from e
    except Exception as e:
        error_msg = f"{operation} failed unexpectedly for {path_str}: {e}"
        logger.error(error_msg)
        raise FileOperationError(message=error_msg, path=path, operation=operation, cause=e) from e


def safe_subprocess_capture(
    cmd: str | list[str],
    *,
    config: SubprocessConfig | None = None,
    operation: str | None = None,
    log_command: bool = False,
) -> tuple[int, str, str]:
    """Run subprocess with output capture and return exit code, stdout, stderr.

    This is a convenience wrapper around safe_subprocess_run for cases where you
    need to handle both success and failure cases and want structured output.

    Args:
        cmd: Command to run (string or list of strings)
        config: SubprocessConfig object containing execution options, or None for defaults
        operation: Operation name for logging and error messages
        log_command: Whether to log the command being executed

    Returns:
        Tuple of (exit_code, stdout, stderr)

    Raises:
        SubprocessError: On execution errors (not on non-zero exit codes)
    """
    try:
        # Create config for capture mode if not provided
        if config is None:
            capture_config = SubprocessConfig(
                cmd=cmd,
                capture_output=True,
                text=True,
                check=False,  # Don't raise on non-zero exit
            )
        else:
            capture_config = SubprocessConfig(
                cmd=cmd,
                cwd=config.cwd,
                env=config.env,
                timeout=config.timeout,
                capture_output=True,
                text=True,
                check=False,  # Don't raise on non-zero exit
            )

        result = safe_subprocess_run(
            cmd,
            config=capture_config,
            operation=operation,
            log_command=log_command,
        )
        return result.returncode, result.stdout or "", result.stderr or ""
    except SubprocessError as e:
        # Re-raise execution errors, but not exit code errors
        if (
            e.exit_code in (124, 127)
            or e.cause
            and not isinstance(e.cause, subprocess.CalledProcessError)
        ):
            raise
        # If it's a CalledProcessError, return the captured output
        return e.exit_code or 1, e.stdout or "", e.stderr or ""


# Enhanced file operation wrappers that use the existing FileOperations but with consistent logging
def safe_write_file(
    path: Path | str,
    content: str,
    *,
    encoding: str = "utf-8",
    operation: str | None = None,
    log_operations: bool = False,
) -> None:
    """Write file safely with consistent error handling and logging.

    Args:
        path: File path to write
        content: Content to write
        encoding: File encoding
        operation: Operation name for logging
        log_operations: Whether to log the operation

    Raises:
        FileOperationError: If file cannot be written
    """
    path_obj = Path(path)
    operation_name = operation or "write file"

    with safe_file_operation(operation_name, path_obj, log_operations):
        FileOperations.atomic_write(path_obj, content, encoding)


def safe_read_file(
    path: Path | str,
    *,
    encoding: str = "utf-8",
    default: str | None = None,
    operation: str | None = None,
    log_operations: bool = False,
) -> str:
    """Read file safely with consistent error handling and logging.

    Args:
        path: File path to read
        encoding: File encoding
        default: Default value if file cannot be read
        operation: Operation name for logging
        log_operations: Whether to log the operation

    Returns:
        File content as string

    Raises:
        FileOperationError: If file cannot be read and no default provided
    """
    path_obj = Path(path)
    operation_name = operation or "read file"

    with safe_file_operation(operation_name, path_obj, log_operations):
        return FileOperations.safe_read_text(path_obj, encoding, default)


def safe_ensure_directory(
    path: Path | str,
    *,
    operation: str | None = None,
    log_operations: bool = False,
) -> None:
    """Ensure directory exists with consistent error handling and logging.

    Args:
        path: Directory path to ensure exists
        operation: Operation name for logging
        log_operations: Whether to log the operation

    Raises:
        FileOperationError: If directory cannot be created
    """
    path_obj = Path(path)
    operation_name = operation or "create directory"

    with safe_file_operation(operation_name, path_obj, log_operations):
        FileOperations.ensure_directory(path_obj)
