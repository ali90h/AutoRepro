"""Tests for decorator utilities."""

import logging
import time

import pytest

from autorepro.utils.decorators import (
    dry_run_aware,
    format_output,
    handle_errors,
    log_operation,
    time_execution,
    validate_args,
)


class TestDryRunAware:
    """Test dry-run aware decorator."""

    def test_dry_run_mode_skips_execution(self, capsys):
        """Test that dry-run mode skips execution and prints message."""

        @dry_run_aware(operation="test operation")
        def sample_function(dry_run: bool = False):
            print("This should not be printed in dry-run mode")
            return 42

        result = sample_function(dry_run=True)
        captured = capsys.readouterr()

        assert result == 0  # Default return code
        assert "Would test operation" in captured.out
        assert "This should not be printed" not in captured.out

    def test_normal_mode_executes_function(self, capsys):
        """Test that normal mode executes the function."""

        @dry_run_aware(operation="test operation")
        def sample_function(dry_run: bool = False):
            print("Function executed")
            return 42

        result = sample_function(dry_run=False)
        captured = capsys.readouterr()

        assert result == 42
        assert "Function executed" in captured.out
        assert "Would test operation" not in captured.out

    def test_custom_return_code(self):
        """Test custom return code for dry-run mode."""

        @dry_run_aware(operation="test", return_code=99)
        def sample_function(dry_run: bool = False):
            return 42

        result = sample_function(dry_run=True)
        assert result == 99

    def test_positional_dry_run_argument(self, capsys):
        """Test dry-run detection with positional arguments."""

        @dry_run_aware(operation="test operation")
        def sample_function(arg1, dry_run: bool = False):
            return "executed"

        result = sample_function("test", True)
        captured = capsys.readouterr()

        assert result == 0
        assert "Would test operation" in captured.out


class TestHandleErrors:
    """Test error handling decorator."""

    def test_successful_execution(self):
        """Test successful function execution."""

        @handle_errors()
        def sample_function():
            return 42

        result = sample_function()
        assert result == 42

    def test_mapped_exception_handling(self):
        """Test handling of mapped exceptions."""

        @handle_errors({ValueError: 2, TypeError: 3})
        def sample_function(error_type):
            if error_type == "value":
                raise ValueError("Test error")
            elif error_type == "type":
                raise TypeError("Test error")
            return 42

        assert sample_function("value") == 2
        assert sample_function("type") == 3
        assert sample_function("none") == 42

    def test_unmapped_exception_handling(self):
        """Test handling of unmapped exceptions."""

        @handle_errors({ValueError: 2}, default_return=99)
        def sample_function():
            raise RuntimeError("Unmapped error")

        result = sample_function()
        assert result == 99

    def test_error_logging(self, caplog):
        """Test error logging functionality."""
        with caplog.at_level(logging.ERROR):

            @handle_errors(log_errors=True)
            def sample_function():
                raise ValueError("Test error message")

            result = sample_function()

        assert result == 2  # Default mapping for ValueError
        assert "Error in sample_function" in caplog.text
        assert "Test error message" in caplog.text

    def test_no_error_logging(self, caplog):
        """Test disabling error logging."""
        with caplog.at_level(logging.ERROR):

            @handle_errors(log_errors=False)
            def sample_function():
                raise ValueError("Test error")

            result = sample_function()

        assert result == 2
        assert not caplog.records


class TestValidateArgs:
    """Test argument validation decorator."""

    def test_successful_validation(self):
        """Test successful argument validation."""

        @validate_args(required=["name"])
        def sample_function(name: str, age: int = 25):
            return f"{name} is {age}"

        result = sample_function("Alice")
        assert result == "Alice is 25"

    def test_missing_required_argument(self, caplog):
        """Test handling of missing required arguments."""
        with caplog.at_level(logging.ERROR):

            @validate_args(required=["name"])
            def sample_function(name: str = None):
                return f"Hello {name}"

            result = sample_function()

        assert result == 2
        assert "Required argument 'name' is empty" in caplog.text

    def test_empty_string_argument(self, caplog):
        """Test handling of empty string arguments."""
        with caplog.at_level(logging.ERROR):

            @validate_args(required=["name"])
            def sample_function(name: str):
                return f"Hello {name}"

            result = sample_function("")

        assert result == 2
        assert "Required argument 'name' is empty" in caplog.text

    def test_custom_validator(self, caplog):
        """Test custom validation function."""

        def custom_validator(args):
            if args.get("age", 0) < 0:
                return False, "Age cannot be negative"
            return True, ""

        with caplog.at_level(logging.ERROR):

            @validate_args(custom_validator=custom_validator)
            def sample_function(age: int = 0):
                return f"Age: {age}"

            result = sample_function(age=-5)

        assert result == 2
        assert "Age cannot be negative" in caplog.text


class TestLogOperation:
    """Test operation logging decorator."""

    def test_basic_logging(self, caplog):
        """Test basic operation logging."""
        with caplog.at_level(logging.INFO):

            @log_operation("test operation")
            def sample_function():
                return 42

            result = sample_function()

        assert result == 42
        assert "Starting test operation" in caplog.text
        assert "Completed test operation successfully" in caplog.text

    def test_logging_with_exception(self, caplog):
        """Test logging when function raises exception."""
        with caplog.at_level(logging.INFO):  # Capture both INFO and ERROR

            @log_operation("test operation")
            def sample_function():
                raise ValueError("Test error")

            with pytest.raises(ValueError):
                sample_function()

        assert "Starting test operation" in caplog.text
        assert "Failed test operation" in caplog.text

    def test_argument_logging(self, caplog):
        """Test logging of function arguments."""
        with caplog.at_level(logging.INFO):

            @log_operation("test operation", log_args=True)
            def sample_function(arg1, arg2="default"):
                return "result"

            result = sample_function("value1", arg2="value2")

        assert result == "result"
        assert "test operation arguments" in caplog.text
        assert "arg2" in caplog.text

    def test_result_logging(self, caplog):
        """Test logging of function results."""
        with caplog.at_level(logging.INFO):

            @log_operation("test operation", log_result=True)
            def sample_function():
                return "test result"

            result = sample_function()

        assert result == "test result"
        assert "test operation result: test result" in caplog.text

    def test_sensitive_argument_filtering(self, caplog):
        """Test that sensitive arguments are not logged."""
        with caplog.at_level(logging.INFO):

            @log_operation("test operation", log_args=True)
            def sample_function(username, password, token):
                return "authenticated"

            result = sample_function("user", "secret", "abc123")

        assert result == "authenticated"
        # Sensitive arguments should not be logged
        assert "secret" not in caplog.text
        assert "abc123" not in caplog.text
        assert "username" in caplog.text


class TestTimeExecution:
    """Test execution timing decorator."""

    def test_timing_below_threshold(self, caplog):
        """Test that fast operations are not logged."""
        with caplog.at_level(logging.INFO):

            @time_execution(log_threshold=1.0)
            def fast_function():
                return "done"

            result = fast_function()

        assert result == "done"
        # Should not log timing info for fast operations
        assert "completed in" not in caplog.text

    def test_timing_above_threshold(self, caplog):
        """Test that slow operations are logged."""
        with caplog.at_level(logging.INFO):

            @time_execution(log_threshold=0.001)  # Very low threshold
            def slow_function():
                time.sleep(0.01)  # 10ms delay
                return "done"

            result = slow_function()

        assert result == "done"
        # Should log timing info for operations above threshold
        assert "slow_function completed in" in caplog.text

    def test_custom_operation_name(self, caplog):
        """Test custom operation name in timing logs."""
        with caplog.at_level(logging.INFO):

            @time_execution(log_threshold=0.001, operation_name="custom operation")
            def sample_function():
                time.sleep(0.01)
                return "done"

            result = sample_function()

        assert result == "done"
        assert "custom operation completed in" in caplog.text

    def test_timing_with_exception(self, caplog):
        """Test that timing works even when function raises exception."""
        with caplog.at_level(logging.INFO):

            @time_execution(log_threshold=0.001)
            def failing_function():
                time.sleep(0.01)
                raise ValueError("Test error")

            with pytest.raises(ValueError):
                failing_function()

        # Should still log timing even when exception occurs
        assert "failing_function completed in" in caplog.text


class TestFormatOutput:
    """Test output formatting decorator."""

    def test_format_output_passthrough(self):
        """Test that format_output currently passes through."""

        @format_output(formats=["json", "text"])
        def sample_function(format_type="text"):
            return f"Output in {format_type} format"

        result = sample_function("json")
        assert result == "Output in json format"


class TestDecoratorStacking:
    """Test combining multiple decorators."""

    def test_multiple_decorators(self, caplog):
        """Test stacking multiple decorators."""
        with caplog.at_level(logging.INFO):

            @time_execution(log_threshold=0.001)
            @handle_errors({ValueError: 3})
            @log_operation("complex operation")
            def complex_function(should_fail: bool = False):
                time.sleep(0.01)
                if should_fail:
                    raise ValueError("Intentional failure")
                return "success"

            # Test successful execution
            result = complex_function()
            assert result == "success"
            assert "Starting complex operation" in caplog.text
            assert "Completed complex operation successfully" in caplog.text
            assert "complex_function completed in" in caplog.text

            # Test error handling
            caplog.clear()
            result = complex_function(should_fail=True)
            assert result == 3  # Error return code
            assert "Failed complex operation" in caplog.text
