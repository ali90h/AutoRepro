#!/usr/bin/env python3
"""
Decorator utilities for cross-cutting concerns in AutoRepro CLI commands.

This module provides decorators to handle common patterns across CLI commands:
- Dry-run mode handling
- Error handling and return codes
- Argument validation
- Operation logging
- Execution timing
- Output formatting
"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable

__all__ = [
    "dry_run_aware",
    "handle_errors",
    "validate_args",
    "log_operation",
    "time_execution",
    "format_output",
]


# Configure logging for the autorepro package to ensure proper test capturing
def _setup_logger():
    """Setup logger with appropriate handlers and propagation for testing."""
    logger = logging.getLogger("autorepro")

    # Set level to DEBUG to capture all log messages
    logger.setLevel(logging.DEBUG)

    # Ensure propagation is enabled for pytest's caplog
    logger.propagate = True

    # Only add handler if none exists to avoid duplicates
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s %(name)s: %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Initialize the logger
_pkg_logger = _setup_logger()


def dry_run_aware(
    message_template: str = "Would {operation}",
    operation: str = "execute command",
    return_code: int = 0,
) -> Callable:
    """
    Skip actual execution when dry_run=True and print what would be done.

    Args:
        message_template: Template for dry-run message, with {operation} placeholder
        operation: Description of what operation would be performed
        return_code: Return code for dry-run mode (default: 0)

    Usage:
        @dry_run_aware(operation="generate plan", return_code=0)
        def cmd_plan(dry_run: bool, ...):
            # This will be skipped if dry_run=True
            return actual_plan_generation()
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract dry_run parameter from kwargs or function signature
            dry_run = kwargs.get("dry_run", False)

            # Check positional arguments for dry_run if not in kwargs
            if not dry_run and hasattr(func, "__code__"):
                arg_names = func.__code__.co_varnames[: func.__code__.co_argcount]
                if "dry_run" in arg_names:
                    try:
                        dry_run_index = arg_names.index("dry_run")
                        if dry_run_index < len(args):
                            dry_run = args[dry_run_index]
                    except (ValueError, IndexError):
                        pass

            if dry_run:
                # Maintain CLI-facing print for dry-run messaging per tests
                print(message_template.format(operation=operation))
                return return_code

            return func(*args, **kwargs)

        return wrapper

    return decorator


def handle_errors(
    error_mappings: dict[type, int] | None = None,
    default_return: int = 1,
    log_errors: bool = True,
) -> Callable:
    """
    Handle common exceptions with appropriate return codes and logging.

    Args:
        error_mappings: Map exception types to return codes
        default_return: Default return code for unmapped exceptions
        log_errors: Whether to log errors using the logger

    Usage:
        @handle_errors({
            ValueError: 2,
            FileNotFoundError: 3,
            PermissionError: 1,
        })
        def cmd_plan(...):
            # Exceptions will be caught and converted to return codes
            pass
    """
    if error_mappings is None:
        error_mappings = {
            ValueError: 2,
            FileNotFoundError: 3,
            PermissionError: 1,
            OSError: 1,
        }

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_errors:
                    log = logging.getLogger("autorepro")
                    log.error(f"Error in {func.__name__}: {e}")

                # Find matching exception type (including parent classes)
                for exc_type, return_code in error_mappings.items():
                    if isinstance(e, exc_type):
                        return return_code

                return default_return

        return wrapper

    return decorator


def validate_args(
    required: list[str] | None = None,
    custom_validator: Callable | None = None,
) -> Callable:
    """
    Validate function arguments and return early with error codes on validation failure.

    Args:
        required: List of required argument names
        custom_validator: Custom validation function that takes kwargs and returns (bool, str)

    Usage:
        @validate_args(required=['desc'])
        def cmd_plan(desc: str = None, file: str = None, ...):
            # desc will be validated as required
            pass
    """
    if required is None:
        required = []

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            log = logging.getLogger("autorepro")

            # Get function signature for argument names
            import inspect

            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()

            # Check required arguments
            for arg_name in required:
                if arg_name not in bound_args.arguments:
                    log.error(f"Required argument '{arg_name}' not provided")
                    return 2

                value = bound_args.arguments[arg_name]
                if value is None or (isinstance(value, str) and not value.strip()):
                    log.error(f"Required argument '{arg_name}' is empty")
                    return 2

            # Run custom validator if provided
            if custom_validator:
                is_valid, error_msg = custom_validator(bound_args.arguments)
                if not is_valid:
                    log.error(f"Validation failed: {error_msg}")
                    return 2

            return func(*args, **kwargs)

        return wrapper

    return decorator


def log_operation(
    operation_name: str,
    log_level: str = "INFO",
    log_args: bool = False,
    log_result: bool = False,
) -> Callable:
    """
    Log operation start, completion, and optionally arguments/results.

    Args:
        operation_name: Human-readable name of the operation
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_args: Whether to log function arguments
        log_result: Whether to log return value

    Usage:
        @log_operation("plan generation", log_level="INFO")
        def cmd_plan(...):
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            log = logging.getLogger("autorepro")
            log_func = getattr(log, log_level.lower())

            # Include operation name as structured context
            log_func(f"Starting {operation_name}", extra={"operation": operation_name})

            if log_args:
                # Sanitize arguments (don't log sensitive data)
                import inspect

                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()
                safe_args = {
                    k: v
                    for k, v in bound_args.arguments.items()
                    if k not in ["password", "token", "secret"]
                }
                log_func(
                    f"{operation_name} arguments: {safe_args}",
                    extra={"operation": operation_name, "arguments": safe_args},
                )

            try:
                result = func(*args, **kwargs)
                log_func(
                    f"Completed {operation_name} successfully",
                    extra={"operation": operation_name},
                )

                if log_result and result is not None:
                    log_func(
                        f"{operation_name} result: {result}",
                        extra={"operation": operation_name, "result": result},
                    )

                return result
            except Exception as e:
                log.error(
                    f"Failed {operation_name}: {e}",
                    extra={"operation": operation_name, "error": str(e)},
                )
                raise

        return wrapper

    return decorator


def time_execution(
    log_threshold: float = 0.1,
    operation_name: str | None = None,
) -> Callable:
    """
    Measure and log execution time for operations.

    Args:
        log_threshold: Minimum execution time (seconds) to log
        operation_name: Custom operation name (defaults to function name)

    Usage:
        @time_execution(log_threshold=1.0)
        def cmd_plan(...):
            pass
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                execution_time = time.time() - start_time

                if execution_time >= log_threshold:
                    log = logging.getLogger("autorepro")
                    op_name = operation_name or func.__name__
                    log.info(
                        f"{op_name} completed in {execution_time:.2f}s",
                        extra={
                            "operation": op_name,
                            "duration_s": round(execution_time, 3),
                        },
                    )

        return wrapper

    return decorator


def format_output(
    formats: list[str] | None = None,
    default_format: str = "text",
) -> Callable:
    """
    Handle output formatting based on format parameter.

    Args:
        formats: List of supported formats
        default_format: Default format if none specified

    Note: This is a placeholder for future output formatting standardization.
    Current implementation passes through to allow gradual adoption.
    """
    if formats is None:
        formats = ["text", "json"]

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # For now, just pass through - full implementation would handle
            # standardized output formatting across all commands
            return func(*args, **kwargs)

        return wrapper

    return decorator
