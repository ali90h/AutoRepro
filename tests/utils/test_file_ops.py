"""
Tests for autorepro.utils.file_ops module.

These tests validate the file operation utilities that replace duplicate
patterns found across the AutoRepro codebase.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from autorepro.utils.file_ops import FileOperations, create_temp_file


class TestFileOperations:
    """Test FileOperations utility class."""

    def test_ensure_directory_creates_new_directory(self):
        """Test ensure_directory creates new directory with parents."""
        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / "new" / "nested" / "dir"

            FileOperations.ensure_directory(target_path)

            assert target_path.exists()
            assert target_path.is_dir()

    def test_ensure_directory_idempotent_with_existing(self):
        """Test ensure_directory is idempotent with existing directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / "existing"
            target_path.mkdir()

            # Should not raise error
            FileOperations.ensure_directory(target_path)

            assert target_path.exists()
            assert target_path.is_dir()

    @patch("pathlib.Path.mkdir")
    def test_ensure_directory_handles_permission_error(self, mock_mkdir):
        """Test ensure_directory raises OSError on permission failure."""
        mock_mkdir.side_effect = PermissionError("Access denied")

        with pytest.raises(OSError, match="Cannot create directory"):
            FileOperations.ensure_directory(Path("/fake/path"))

    def test_atomic_write_creates_file_successfully(self):
        """Test atomic_write creates file with correct content."""
        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / "test.txt"
            content = "Hello, World!\nSecond line."

            FileOperations.atomic_write(target_path, content)

            assert target_path.exists()
            assert target_path.read_text(encoding="utf-8") == content

    def test_atomic_write_creates_parent_directories(self):
        """Test atomic_write creates parent directories if needed."""
        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / "nested" / "dir" / "test.txt"
            content = "Test content"

            FileOperations.atomic_write(target_path, content)

            assert target_path.exists()
            assert target_path.read_text(encoding="utf-8") == content

    def test_atomic_write_overwrites_existing_file(self):
        """Test atomic_write overwrites existing file atomically."""
        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / "existing.txt"
            target_path.write_text("Old content", encoding="utf-8")

            new_content = "New content"
            FileOperations.atomic_write(target_path, new_content)

            assert target_path.read_text(encoding="utf-8") == new_content

    def test_atomic_write_uses_custom_encoding(self):
        """Test atomic_write respects custom encoding parameter."""
        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / "utf16.txt"
            content = "Content with unicode: 你好"

            FileOperations.atomic_write(target_path, content, encoding="utf-16")

            # Verify file was written with correct encoding
            assert target_path.read_text(encoding="utf-16") == content

    @patch("autorepro.utils.file_ops.FileOperations.ensure_directory")
    def test_atomic_write_cleans_up_temp_on_error(self, mock_ensure_dir):
        """Test atomic_write cleans up temp file on write error."""
        mock_ensure_dir.side_effect = OSError("Permission denied")

        with tempfile.TemporaryDirectory() as temp_dir:
            target_path = Path(temp_dir) / "test.txt"

            with pytest.raises(OSError, match="Failed to write file"):
                FileOperations.atomic_write(target_path, "content")

            # Verify no temp files left behind
            temp_files = list(Path(temp_dir).glob("*.tmp"))
            assert len(temp_files) == 0

    def test_safe_read_text_reads_existing_file(self):
        """Test safe_read_text reads existing file successfully."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir) / "test.txt"
            expected_content = "Line 1\nLine 2\nLine 3"
            test_path.write_text(expected_content, encoding="utf-8")

            content = FileOperations.safe_read_text(test_path)

            assert content == expected_content

    def test_safe_read_text_returns_default_on_missing_file(self):
        """Test safe_read_text returns default for missing file."""
        missing_path = Path("/nonexistent/file.txt")
        default_content = "Default content"

        content = FileOperations.safe_read_text(missing_path, default=default_content)

        assert content == default_content

    def test_safe_read_text_raises_on_missing_file_no_default(self):
        """Test safe_read_text raises OSError for missing file when no default."""
        missing_path = Path("/nonexistent/file.txt")

        with pytest.raises(OSError, match="Failed to read file"):
            FileOperations.safe_read_text(missing_path)

    def test_safe_read_text_uses_custom_encoding(self):
        """Test safe_read_text respects custom encoding."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_path = Path(temp_dir) / "utf16.txt"
            content = "Unicode content: 你好"
            test_path.write_text(content, encoding="utf-16")

            read_content = FileOperations.safe_read_text(test_path, encoding="utf-16")

            assert read_content == content

    def test_safe_read_json_reads_valid_json(self):
        """Test safe_read_json reads valid JSON file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "test.json"
            test_data = {"key": "value", "number": 42, "list": [1, 2, 3]}
            json_path.write_text(json.dumps(test_data), encoding="utf-8")

            data = FileOperations.safe_read_json(json_path)

            assert data == test_data

    def test_safe_read_json_returns_default_on_invalid_json(self):
        """Test safe_read_json returns default for invalid JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "invalid.json"
            json_path.write_text("{ invalid json", encoding="utf-8")

            default_data = {"default": True}
            data = FileOperations.safe_read_json(json_path, default=default_data)

            assert data == default_data

    def test_safe_read_json_returns_default_on_missing_file(self):
        """Test safe_read_json returns default for missing file."""
        missing_path = Path("/nonexistent/file.json")
        default_data = {"missing": True}

        data = FileOperations.safe_read_json(missing_path, default=default_data)

        assert data == default_data

    def test_safe_read_json_raises_on_error_no_default(self):
        """Test safe_read_json raises error when no default provided."""
        missing_path = Path("/nonexistent/file.json")

        with pytest.raises(OSError):
            FileOperations.safe_read_json(missing_path)

    def test_atomic_write_json_writes_formatted_json(self):
        """Test atomic_write_json writes properly formatted JSON."""
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "output.json"
            test_data = {"b_key": "value", "a_key": 42}

            FileOperations.atomic_write_json(json_path, test_data)

            content = json_path.read_text(encoding="utf-8")

            # Verify formatting (indented, sorted keys, trailing newline)
            assert content.endswith("\n")
            assert '"a_key"' in content
            assert '"b_key"' in content
            # Verify it's valid JSON
            parsed = json.loads(content)
            assert parsed == test_data

    def test_atomic_write_json_custom_formatting(self):
        """Test atomic_write_json respects custom formatting parameters."""
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "custom.json"
            test_data = {"key": "value"}

            FileOperations.atomic_write_json(
                json_path, test_data, indent=4, sort_keys=False, ensure_ascii=True
            )

            content = json_path.read_text(encoding="utf-8")
            parsed = json.loads(content)
            assert parsed == test_data

    def test_atomic_write_json_handles_serialization_error(self):
        """Test atomic_write_json raises OSError on serialization failure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            json_path = Path(temp_dir) / "error.json"
            # Object that can't be JSON serialized
            unserializable_data = {"func": lambda x: x}

            with pytest.raises(OSError, match="Failed to serialize JSON data"):
                FileOperations.atomic_write_json(json_path, unserializable_data)


class TestCreateTempFile:
    """Test create_temp_file utility function."""

    def test_create_temp_file_with_content(self):
        """Test create_temp_file creates file with correct content."""
        content = "Temporary file content\nMultiple lines"

        temp_path = create_temp_file(content)

        try:
            assert temp_path.exists()
            assert temp_path.read_text(encoding="utf-8") == content
        finally:
            # Cleanup
            if temp_path.exists():
                temp_path.unlink()

    def test_create_temp_file_with_suffix(self):
        """Test create_temp_file creates file with correct suffix."""
        content = "JSON content"
        suffix = ".json"

        temp_path = create_temp_file(content, suffix=suffix)

        try:
            assert temp_path.exists()
            assert str(temp_path).endswith(suffix)
            assert temp_path.read_text(encoding="utf-8") == content
        finally:
            # Cleanup
            if temp_path.exists():
                temp_path.unlink()

    def test_create_temp_file_with_custom_encoding(self):
        """Test create_temp_file respects custom encoding."""
        content = "Unicode: 你好"

        temp_path = create_temp_file(content, encoding="utf-16")

        try:
            assert temp_path.exists()
            assert temp_path.read_text(encoding="utf-16") == content
        finally:
            # Cleanup
            if temp_path.exists():
                temp_path.unlink()

    def test_create_temp_file_caller_responsible_for_cleanup(self):
        """Test create_temp_file doesn't auto-delete (caller responsible)."""
        content = "Persistent temp content"

        temp_path = create_temp_file(content)

        # File should still exist after function returns
        assert temp_path.exists()

        # Cleanup (simulating caller responsibility)
        temp_path.unlink()
        assert not temp_path.exists()
