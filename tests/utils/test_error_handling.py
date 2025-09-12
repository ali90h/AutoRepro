"""
Tests for autorepro.utils.error_handling module.

These tests validate the standardized error handling utilities that replace scattered
exception handling patterns across the AutoRepro codebase.
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from autorepro.utils.error_handling import (
    AutoReproError,
    FileOperationError,
    SubprocessDetails,
    SubprocessError,
    safe_ensure_directory,
    safe_file_operation,
    safe_read_file,
    safe_subprocess_capture,
    safe_write_file,
)
from autorepro.utils.error_handling import (
    safe_subprocess_run_simple as safe_subprocess_run,
)
from autorepro.utils.process import SubprocessConfig


class TestStandardizedExceptions:
    """Test standardized exception classes."""

    def test_autorepro_error_base(self):
        """Test AutoReproError base exception."""
        error = AutoReproError("test message", operation="test_op")
        assert str(error) == "test message"
        assert error.message == "test message"
        assert error.operation == "test_op"
        assert error.cause is None

    def test_subprocess_error_attributes(self):
        """Test SubprocessError attributes and initialization."""
        cmd = ["echo", "test"]
        details = SubprocessDetails(
            cmd=cmd, exit_code=1, stdout="output", stderr="error"
        )
        error = SubprocessError(
            message="test failed",
            details=details,
            operation="test",
        )
        assert str(error) == "test failed"
        assert error.cmd == "echo test"
        assert error.exit_code == 1
        assert error.stdout == "output"
        assert error.stderr == "error"
        assert error.operation == "test"

    def test_subprocess_error_string_command(self):
        """Test SubprocessError with string command."""
        details = SubprocessDetails(cmd="echo test")
        error = SubprocessError(message="test failed", details=details)
        assert error.cmd == "echo test"

    def test_file_operation_error_attributes(self):
        """Test FileOperationError attributes and initialization."""
        path = Path("/test/path")
        error = FileOperationError(message="file failed", path=path, operation="read")
        assert str(error) == "file failed"
        assert error.path == path
        assert error.operation == "read"

    def test_file_operation_error_string_path(self):
        """Test FileOperationError with string path."""
        error = FileOperationError(message="test failed", path="/test/path")
        assert error.path == Path("/test/path")


class TestSafeSubprocessRun:
    """Test safe_subprocess_run wrapper function."""

    def test_successful_command_execution(self):
        """Test successful command execution."""
        result = safe_subprocess_run(["echo", "hello"], check=False)
        assert result.returncode == 0
        assert result.stdout.strip() == "hello"

    def test_failed_command_with_check_false(self):
        """Test failed command with check=False doesn't raise."""
        result = safe_subprocess_run(["false"], check=False)
        assert result.returncode == 1

    def test_failed_command_with_check_true_raises(self):
        """Test failed command with check=True raises SubprocessError."""
        with pytest.raises(SubprocessError) as exc_info:
            safe_subprocess_run(["false"], check=True, operation="test_op")

        error = exc_info.value
        assert "test_op failed" in error.message
        assert error.exit_code == 1
        assert error.operation == "test_op"
        assert isinstance(error.cause, subprocess.CalledProcessError)

    def test_command_not_found_raises(self):
        """Test command not found raises SubprocessError."""
        with pytest.raises(SubprocessError) as exc_info:
            safe_subprocess_run(["nonexistent_command_12345"], operation="test_op")

        error = exc_info.value
        assert "command not found" in error.message.lower()
        assert error.exit_code == 127
        assert error.operation == "test_op"
        assert isinstance(error.cause, FileNotFoundError)

    def test_timeout_handling(self):
        """Test command timeout handling."""
        with pytest.raises(SubprocessError) as exc_info:
            safe_subprocess_run(["sleep", "10"], timeout=0.1, operation="timeout_test")

        error = exc_info.value
        assert "timed out" in error.message.lower()
        assert error.exit_code == 124
        assert error.operation == "timeout_test"
        assert isinstance(error.cause, subprocess.TimeoutExpired)

    def test_string_command_conversion(self):
        """Test string command is properly converted."""
        result = safe_subprocess_run("echo hello", check=False)
        assert result.returncode == 0
        assert result.stdout.strip() == "hello"

    def test_operation_logging(self, caplog):
        """Test operation logging when enabled."""
        caplog.set_level(logging.DEBUG, logger="autorepro.utils.error_handling")
        safe_subprocess_run(
            ["echo", "test"], operation="test_op", log_command=True, check=False
        )

        assert "Running test_op: echo test" in caplog.text

    def test_working_directory_parameter(self):
        """Test working directory parameter is handled correctly."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = safe_subprocess_run(["pwd"], cwd=temp_dir, check=False)
            assert result.returncode == 0
            assert temp_dir in result.stdout.strip()


class TestSafeSubprocessCapture:
    """Test safe_subprocess_capture convenience function."""

    def test_successful_command_capture(self):
        """Test successful command output capture."""
        exit_code, stdout, stderr = safe_subprocess_capture(["echo", "hello"])
        assert exit_code == 0
        assert stdout.strip() == "hello"
        assert stderr == ""

    def test_failed_command_capture(self):
        """Test failed command output capture."""
        exit_code, stdout, stderr = safe_subprocess_capture(["false"])
        assert exit_code == 1
        assert stdout == ""

    def test_command_not_found_raises(self):
        """Test command not found still raises exception."""
        with pytest.raises(SubprocessError):
            safe_subprocess_capture(["nonexistent_command_12345"])

    def test_timeout_raises(self):
        """Test timeout still raises exception."""
        with pytest.raises(SubprocessError):
            config = SubprocessConfig(cmd=["sleep", "10"], timeout=0.1)
            safe_subprocess_capture(["sleep", "10"], config=config)


class TestSafeFileOperation:
    """Test safe_file_operation context manager."""

    def test_successful_operation(self):
        """Test successful file operation doesn't raise."""
        with safe_file_operation("test operation"):
            # No file operations, should complete successfully
            pass

    def test_os_error_handling(self):
        """Test OSError is converted to FileOperationError."""
        with pytest.raises(FileOperationError) as exc_info:
            with safe_file_operation("test operation", path="/test/path"):
                raise OSError("test error")

        error = exc_info.value
        assert "test operation failed" in error.message
        assert error.path == Path("/test/path")
        assert error.operation == "test operation"
        assert isinstance(error.cause, OSError)

    def test_permission_error_handling(self):
        """Test PermissionError is converted to FileOperationError."""
        with pytest.raises(FileOperationError) as exc_info:
            with safe_file_operation("test operation"):
                raise PermissionError("permission denied")

        error = exc_info.value
        assert "test operation failed" in error.message
        assert isinstance(error.cause, PermissionError)

    def test_unicode_error_handling(self):
        """Test UnicodeDecodeError is converted to FileOperationError."""
        with pytest.raises(FileOperationError) as exc_info:
            with safe_file_operation("test operation"):
                raise UnicodeDecodeError("utf-8", b"", 0, 1, "test")

        error = exc_info.value
        assert "test operation failed" in error.message
        assert isinstance(error.cause, UnicodeDecodeError)

    def test_unexpected_error_handling(self):
        """Test unexpected errors are converted to FileOperationError."""
        with pytest.raises(FileOperationError) as exc_info:
            with safe_file_operation("test operation"):
                raise ValueError("unexpected error")

        error = exc_info.value
        assert "test operation failed unexpectedly" in error.message
        assert isinstance(error.cause, ValueError)

    def test_operation_logging(self, caplog):
        """Test operation logging when enabled."""
        caplog.set_level(logging.DEBUG, logger="autorepro.utils.error_handling")
        with safe_file_operation("test operation", log_operations=True):
            pass

        assert "Starting test operation" in caplog.text
        assert "Completed test operation" in caplog.text


class TestSafeFileWrappers:
    """Test safe file operation wrapper functions."""

    def test_safe_write_file(self):
        """Test safe_write_file function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir) / "test.txt"
            content = "Hello, World!"

            safe_write_file(test_path, content)

            assert test_path.exists()
            assert test_path.read_text() == content

    def test_safe_write_file_creates_parent_directory(self):
        """Test safe_write_file creates parent directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir) / "subdir" / "test.txt"
            content = "Hello, World!"

            safe_write_file(test_path, content)

            assert test_path.exists()
            assert test_path.read_text() == content

    def test_safe_read_file_existing(self):
        """Test safe_read_file with existing file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir) / "test.txt"
            content = "Hello, World!"
            test_path.write_text(content)

            result = safe_read_file(test_path)

            assert result == content

    def test_safe_read_file_missing_with_default(self):
        """Test safe_read_file with missing file and default."""
        missing_path = Path("/nonexistent/file.txt")
        default_content = "default"

        result = safe_read_file(missing_path, default=default_content)

        assert result == default_content

    def test_safe_read_file_missing_no_default_raises(self):
        """Test safe_read_file with missing file and no default raises."""
        missing_path = Path("/nonexistent/file.txt")

        with pytest.raises(FileOperationError):
            safe_read_file(missing_path)

    def test_safe_ensure_directory(self):
        """Test safe_ensure_directory function."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir) / "subdir" / "nested"

            safe_ensure_directory(test_path)

            assert test_path.exists()
            assert test_path.is_dir()

    def test_safe_ensure_directory_existing(self):
        """Test safe_ensure_directory with existing directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir)

            # Should not raise even if directory exists
            safe_ensure_directory(test_path)

            assert test_path.exists()
            assert test_path.is_dir()

    def test_file_wrapper_logging(self, caplog):
        """Test file wrapper functions log operations when enabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir) / "test.txt"

            caplog.set_level(logging.DEBUG, logger="autorepro.utils.error_handling")
            safe_write_file(test_path, "test", log_operations=True)
            safe_read_file(test_path, log_operations=True)

            assert "Starting write file" in caplog.text
            assert "Completed write file" in caplog.text
            assert "Starting read file" in caplog.text
            assert "Completed read file" in caplog.text


class TestErrorHandlingIntegration:
    """Test integration between error handling utilities."""

    def test_subprocess_error_in_file_context(self):
        """Test handling subprocess error within file operation context."""
        with pytest.raises(FileOperationError):
            with safe_file_operation("complex operation"):
                # This should be converted to FileOperationError
                raise OSError("simulated file error")

    @patch("autorepro.utils.error_handling.FileOperations.atomic_write")
    def test_safe_write_file_error_handling(self, mock_write):
        """Test safe_write_file error handling."""
        mock_write.side_effect = OSError("write failed")

        with pytest.raises(FileOperationError) as exc_info:
            safe_write_file("/test/path", "content")

        assert "write file failed" in exc_info.value.message
        assert exc_info.value.path == Path("/test/path")

    def test_error_message_consistency(self):
        """Test that error messages follow consistent format."""
        # Test subprocess error format
        with pytest.raises(SubprocessError) as exc_info:
            safe_subprocess_run(["false"], check=True, operation="test_op")
        assert "test_op failed with exit code" in exc_info.value.message

        # Test file operation error format
        with pytest.raises(FileOperationError) as exc_info:
            with safe_file_operation("test_op", path="/test"):
                raise OSError("test error")
        assert "test_op failed for /test" in exc_info.value.message
