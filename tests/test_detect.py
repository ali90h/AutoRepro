"""Tests for language detection functionality."""

import tempfile
from pathlib import Path

from autorepro.detect import detect_languages


class TestDetectLanguages:
    """Test the detect_languages function."""

    def test_empty_directory(self):
        """Test detection in an empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = detect_languages(tmpdir)
            assert result == []

    def test_python_detection_single_file(self):
        """Test Python detection with pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create pyproject.toml
            pyproject_path = Path(tmpdir) / "pyproject.toml"
            pyproject_path.write_text("[build-system]\\nrequires = []")

            result = detect_languages(tmpdir)
            assert result == [("python", ["pyproject.toml"])]

    def test_node_detection_multiple_files(self):
        """Test Node.js detection with multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create package.json and pnpm-lock.yaml
            (Path(tmpdir) / "package.json").write_text('{"name": "test"}')
            (Path(tmpdir) / "pnpm-lock.yaml").write_text("lockfileVersion: 5.4")

            result = detect_languages(tmpdir)
            # Should detect node with both files, sorted alphabetically
            assert result == [("node", ["package.json", "pnpm-lock.yaml"])]

    def test_csharp_glob_detection(self):
        """Test C# detection with .csproj glob pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a .csproj file
            (Path(tmpdir) / "App.csproj").write_text("")

            result = detect_languages(tmpdir)
            assert result == [("csharp", ["App.csproj"])]

    def test_multiple_languages_alphabetical_ordering(self):
        """Test detection of multiple languages with alphabetical ordering."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files for different languages
            (Path(tmpdir) / "pyproject.toml").write_text("[build-system]")  # python
            (Path(tmpdir) / "go.mod").write_text("module test")  # go
            (Path(tmpdir) / "package.json").write_text('{"name": "test"}')  # node

            result = detect_languages(tmpdir)
            # Should be sorted alphabetically by language name
            expected = [
                ("go", ["go.mod"]),
                ("node", ["package.json"]),
                ("python", ["pyproject.toml"]),
            ]
            assert result == expected

    def test_reasons_alphabetical_ordering(self):
        """Test that reasons within a language are sorted alphabetically."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple Python files in reverse alphabetical order
            (Path(tmpdir) / "setup.py").write_text("from setuptools import setup")
            (Path(tmpdir) / "requirements.txt").write_text("requests")
            (Path(tmpdir) / "pyproject.toml").write_text("[build-system]")

            result = detect_languages(tmpdir)
            assert result == [
                ("python", ["pyproject.toml", "requirements.txt", "setup.py"])
            ]

    def test_glob_pattern_with_multiple_matches(self):
        """Test glob patterns that match multiple files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create multiple .py files
            (Path(tmpdir) / "main.py").write_text("print('hello')")
            (Path(tmpdir) / "utils.py").write_text("def helper(): pass")

            result = detect_languages(tmpdir)
            assert result == [("python", ["main.py", "utils.py"])]

    def test_duplicate_matches_removed(self):
        """Test that duplicate matches are removed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create pyproject.toml which matches both exact filename and *.py doesn't exist
            (Path(tmpdir) / "pyproject.toml").write_text("[build-system]")

            result = detect_languages(tmpdir)
            # Should only list pyproject.toml once
            assert result == [("python", ["pyproject.toml"])]

    def test_subdirectories_ignored(self):
        """Test that subdirectories are ignored (root only scan)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file in subdirectory
            subdir = Path(tmpdir) / "subdir"
            subdir.mkdir()
            (subdir / "pyproject.toml").write_text("[build-system]")

            result = detect_languages(tmpdir)
            # Should not detect anything since we only scan root
            assert result == []

    def test_mixed_exact_and_glob_patterns(self):
        """Test language with both exact filenames and glob patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create both exact match and glob match for Python
            (Path(tmpdir) / "setup.py").write_text(
                "from setuptools import setup"
            )  # exact
            (Path(tmpdir) / "main.py").write_text("print('hello')")  # glob *.py

            result = detect_languages(tmpdir)
            assert result == [("python", ["main.py", "setup.py"])]
