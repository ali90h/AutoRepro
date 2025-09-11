"""
Tests for autorepro.utils.cli_validation module.

These tests validate the CLI validation utilities that replace duplicate argument
validation patterns found across AutoRepro CLI commands.
"""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from autorepro.utils.cli_validation import (
    ArgumentValidator,
    ValidationError,
    validate_and_exit,
    validate_multiple,
)


class TestArgumentValidator:
    """Test ArgumentValidator utility class."""

    def test_validate_desc_file_exclusive_valid_desc_only(self):
        """Test validation passes with desc argument only."""
        result = ArgumentValidator.validate_desc_file_exclusive(
            desc="test description", file=None
        )
        assert result is None

    def test_validate_desc_file_exclusive_valid_file_only(self):
        """Test validation passes with file argument only."""
        result = ArgumentValidator.validate_desc_file_exclusive(
            desc=None, file="test.txt"
        )
        assert result is None

    def test_validate_desc_file_exclusive_missing_both(self):
        """Test validation fails when both desc and file are missing."""
        result = ArgumentValidator.validate_desc_file_exclusive(desc=None, file=None)
        assert result is not None
        assert "Either --desc or --file must be specified" in result

    def test_validate_desc_file_exclusive_both_provided(self):
        """Test validation fails when both desc and file are provided."""
        result = ArgumentValidator.validate_desc_file_exclusive(
            desc="test description", file="test.txt"
        )
        assert result is not None
        assert "Cannot use both --desc and --file" in result

    def test_validate_desc_file_exclusive_empty_string_treated_as_none(self):
        """Test empty strings are treated as None values."""
        result = ArgumentValidator.validate_desc_file_exclusive(desc="", file="")
        assert result is not None
        assert "Either --desc or --file must be specified" in result

    def test_validate_output_path_none_value(self):
        """Test output path validation passes for None value."""
        result = ArgumentValidator.validate_output_path(None)
        assert result is None

    def test_validate_output_path_nonexistent_file(self):
        """Test output path validation passes for nonexistent file."""
        result = ArgumentValidator.validate_output_path("/nonexistent/file.txt")
        assert result is None

    def test_validate_output_path_existing_file(self):
        """Test output path validation passes for existing file."""
        with tempfile.NamedTemporaryFile() as temp_file:
            result = ArgumentValidator.validate_output_path(temp_file.name)
            assert result is None

    def test_validate_output_path_existing_directory_fails(self):
        """Test output path validation fails for existing directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = ArgumentValidator.validate_output_path(temp_dir)
            assert result is not None
            assert "Output path cannot be a directory" in result
            assert temp_dir in result

    def test_validate_output_path_path_object(self):
        """Test output path validation works with Path objects."""
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            result = ArgumentValidator.validate_output_path(dir_path)
            assert result is not None
            assert "Output path cannot be a directory" in result

    def test_validate_output_path_invalid_path(self):
        """Test output path validation handles invalid path strings."""
        # Mock Path() in the validation module to raise ValueError to test error handling
        with patch("autorepro.utils.cli_validation.Path") as mock_path:
            mock_path.side_effect = ValueError("Invalid path")

            result = ArgumentValidator.validate_output_path("invalid_path")
            assert result is not None
            assert "Invalid output path" in result

    def test_validate_repo_path_none_value(self):
        """Test repo path validation passes for None value."""
        result = ArgumentValidator.validate_repo_path(None)
        assert result is None

    def test_validate_repo_path_existing_directory(self):
        """Test repo path validation passes for existing directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = ArgumentValidator.validate_repo_path(temp_dir)
            assert result is None

    def test_validate_repo_path_nonexistent_path(self):
        """Test repo path validation fails for nonexistent path."""
        result = ArgumentValidator.validate_repo_path("/nonexistent/path")
        assert result is not None
        assert "Repository path does not exist" in result

    def test_validate_repo_path_existing_file_fails(self):
        """Test repo path validation fails for existing file (not directory)."""
        with tempfile.NamedTemporaryFile() as temp_file:
            result = ArgumentValidator.validate_repo_path(temp_file.name)
            assert result is not None
            assert "Repository path is not a directory" in result

    def test_validate_repo_path_path_object(self):
        """Test repo path validation works with Path objects."""
        with tempfile.TemporaryDirectory() as temp_dir:
            dir_path = Path(temp_dir)
            result = ArgumentValidator.validate_repo_path(dir_path)
            assert result is None

    def test_validate_required_arg_valid_value(self):
        """Test required argument validation passes for valid value."""
        result = ArgumentValidator.validate_required_arg("valid_value", "--test-arg")
        assert result is None

    def test_validate_required_arg_none_value(self):
        """Test required argument validation fails for None value."""
        result = ArgumentValidator.validate_required_arg(None, "--test-arg")
        assert result is not None
        assert "--test-arg must be specified" in result

    def test_validate_required_arg_empty_string(self):
        """Test required argument validation fails for empty string."""
        result = ArgumentValidator.validate_required_arg("", "--test-arg")
        assert result is not None
        assert "--test-arg must be specified" in result

    def test_validate_file_exists_none_value(self):
        """Test file exists validation passes for None value."""
        result = ArgumentValidator.validate_file_exists(None, "Test file")
        assert result is None

    def test_validate_file_exists_existing_file(self):
        """Test file exists validation passes for existing readable file."""
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as temp_file:
            temp_file.write("test content")
            temp_file.flush()

            result = ArgumentValidator.validate_file_exists(temp_file.name, "Test file")
            assert result is None

    def test_validate_file_exists_nonexistent_file(self):
        """Test file exists validation fails for nonexistent file."""
        result = ArgumentValidator.validate_file_exists(
            "/nonexistent/file.txt", "Test file"
        )
        assert result is not None
        assert "Test file does not exist" in result

    def test_validate_file_exists_directory_fails(self):
        """Test file exists validation fails for directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = ArgumentValidator.validate_file_exists(temp_dir, "Test file")
            assert result is not None
            assert "Test file is not a file" in result

    def test_validate_file_exists_unreadable_file(self):
        """Test file exists validation handles unreadable files."""
        with tempfile.NamedTemporaryFile() as temp_file:
            # Write binary data to make it fail UTF-8 decoding
            temp_file.write(b"\xff\xfe\x00\x00")
            temp_file.flush()

            result = ArgumentValidator.validate_file_exists(temp_file.name, "Test file")
            assert result is not None
            assert "Cannot read test file" in result

    def test_validate_file_exists_path_object(self):
        """Test file exists validation works with Path objects."""
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8") as temp_file:
            temp_file.write("test content")
            temp_file.flush()

            file_path = Path(temp_file.name)
            result = ArgumentValidator.validate_file_exists(file_path, "Test file")
            assert result is None

    def test_validate_file_exists_default_arg_name(self):
        """Test file exists validation uses default argument name."""
        result = ArgumentValidator.validate_file_exists("/nonexistent/file.txt")
        assert result is not None
        assert "File does not exist" in result  # Default arg_name is "File"


class TestValidationError:
    """Test ValidationError exception class."""

    def test_validation_error_initialization(self):
        """Test ValidationError initializes with message and exit code."""
        error = ValidationError("Test error", 3)
        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.exit_code == 3

    def test_validation_error_default_exit_code(self):
        """Test ValidationError uses default exit code 2."""
        error = ValidationError("Test error")
        assert error.exit_code == 2


class TestValidationHelpers:
    """Test validation helper functions."""

    def test_validate_and_exit_no_error(self):
        """Test validate_and_exit passes when validator returns None."""
        # Should not raise exception
        validate_and_exit(None)

    def test_validate_and_exit_with_error(self):
        """Test validate_and_exit raises ValidationError when validator fails."""
        with pytest.raises(ValidationError) as exc_info:
            validate_and_exit("Validation failed")

        assert exc_info.value.message == "Validation failed"
        assert exc_info.value.exit_code == 2

    def test_validate_and_exit_custom_exit_code(self):
        """Test validate_and_exit uses custom exit code."""
        with pytest.raises(ValidationError) as exc_info:
            validate_and_exit("Custom error", exit_code=5)

        assert exc_info.value.exit_code == 5

    def test_validate_multiple_no_errors(self):
        """Test validate_multiple passes when all validators return None."""
        # Should not raise exception
        validate_multiple(None, None, None)

    def test_validate_multiple_with_error(self):
        """Test validate_multiple raises ValidationError on first failure."""
        with pytest.raises(ValidationError) as exc_info:
            validate_multiple(None, "First error", "Second error")

        assert exc_info.value.message == "First error"

    def test_validate_multiple_custom_exit_code(self):
        """Test validate_multiple uses custom exit code."""
        with pytest.raises(ValidationError) as exc_info:
            validate_multiple("Error message", exit_code=7)

        assert exc_info.value.exit_code == 7


class TestArgumentValidatorIntegration:
    """Integration tests for ArgumentValidator with mock argument objects."""

    def test_cli_args_integration_pattern(self):
        """Test ArgumentValidator with mock args object (typical CLI usage)."""
        # Mock argparse Namespace object
        valid_args = Mock()
        valid_args.desc = "test description"
        valid_args.file = None
        valid_args.out = "/tmp/output.txt"
        valid_args.repo = None

        # Test multiple validations
        desc_file_error = ArgumentValidator.validate_desc_file_exclusive(
            valid_args.desc, valid_args.file
        )
        output_error = ArgumentValidator.validate_output_path(valid_args.out)
        repo_error = ArgumentValidator.validate_repo_path(valid_args.repo)

        assert desc_file_error is None
        assert output_error is None
        assert repo_error is None

    def test_cli_args_integration_with_errors(self):
        """Test ArgumentValidator catches common CLI error combinations."""
        # Mock args with multiple errors
        invalid_args = Mock()
        invalid_args.desc = "description"
        invalid_args.file = "file.txt"  # Both provided
        invalid_args.out = "/tmp"  # Directory, not file
        invalid_args.repo_slug = None  # Required but missing

        desc_file_error = ArgumentValidator.validate_desc_file_exclusive(
            invalid_args.desc, invalid_args.file
        )
        output_error = ArgumentValidator.validate_output_path(invalid_args.out)
        required_error = ArgumentValidator.validate_required_arg(
            invalid_args.repo_slug, "--repo-slug"
        )

        assert desc_file_error is not None
        assert output_error is not None
        assert required_error is not None

        # Test validate_multiple catches first error
        with pytest.raises(ValidationError) as exc_info:
            validate_multiple(desc_file_error, output_error, required_error)

        assert "Cannot use both --desc and --file" in exc_info.value.message
