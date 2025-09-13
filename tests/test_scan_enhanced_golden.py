"""Tests for enhanced scan functionality with golden files."""

import json
import tempfile
from pathlib import Path

import pytest

from autorepro.cli import main


class TestScanEnhancedGolden:
    """Test enhanced scan functionality against golden files."""

    @pytest.fixture
    def test_repo(self):
        """Create a test repository structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test structure: pyproject.toml at root, package.json in a/b/
            (tmpdir_path / "pyproject.toml").write_text("[build-system]\nrequires = []")
            (tmpdir_path / "a").mkdir()
            (tmpdir_path / "a" / "b").mkdir()
            (tmpdir_path / "a" / "b" / "package.json").write_text("{}")

            yield tmpdir_path

    @pytest.fixture
    def test_repo_with_gitignore(self):
        """Create a test repository structure with .gitignore."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test structure: pyproject.toml at root, package.json in a/b/
            (tmpdir_path / "pyproject.toml").write_text("[build-system]\nrequires = []")
            (tmpdir_path / "a").mkdir()
            (tmpdir_path / "a" / "b").mkdir()
            (tmpdir_path / "a" / "b" / "package.json").write_text("{}")

            # Create .gitignore that ignores the 'a/' directory
            (tmpdir_path / ".gitignore").write_text("a/\n")

            yield tmpdir_path

    def _normalize_json_output(self, output: str, test_root: str) -> dict:
        """Normalize JSON output by replacing the actual root with '.'."""
        result = json.loads(output)
        result["root"] = "."
        return result

    def _load_golden_file(self, filename: str) -> dict:
        """Load a golden file and return parsed JSON."""
        golden_path = Path(__file__).parent / "golden" / "scan" / "enhanced" / filename
        with open(golden_path) as f:
            return json.loads(f.read())

    def test_scan_depth0_golden(self, test_repo, capsys):
        """Test scan --depth 0 against golden file."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(test_repo)

            # Mock sys.argv and run main
            import sys

            original_argv = sys.argv
            sys.argv = ["autorepro", "scan", "--json", "--depth", "0"]

            exit_code = main()
            assert exit_code == 0

            captured = capsys.readouterr()
            actual = self._normalize_json_output(captured.out, str(test_repo))
            expected = self._load_golden_file("SCAN.depth0.json")

            assert actual == expected

        finally:
            sys.argv = original_argv
            os.chdir(original_cwd)

    def test_scan_depth2_golden(self, test_repo, capsys):
        """Test scan --depth 2 against golden file."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(test_repo)

            # Mock sys.argv and run main
            import sys

            original_argv = sys.argv
            sys.argv = ["autorepro", "scan", "--json", "--depth", "2"]

            exit_code = main()
            assert exit_code == 0

            captured = capsys.readouterr()
            actual = self._normalize_json_output(captured.out, str(test_repo))
            expected = self._load_golden_file("SCAN.depth2.json")

            assert actual == expected

        finally:
            sys.argv = original_argv
            os.chdir(original_cwd)

    def test_scan_depth2_ignore_a_golden(self, test_repo, capsys):
        """Test scan --depth 2 --ignore 'a/**' against golden file."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(test_repo)

            # Mock sys.argv and run main
            import sys

            original_argv = sys.argv
            sys.argv = [
                "autorepro",
                "scan",
                "--json",
                "--depth",
                "2",
                "--ignore",
                "a/**",
            ]

            exit_code = main()
            assert exit_code == 0

            captured = capsys.readouterr()
            actual = self._normalize_json_output(captured.out, str(test_repo))
            expected = self._load_golden_file("SCAN.depth2.ignore_a.json")

            assert actual == expected

        finally:
            sys.argv = original_argv
            os.chdir(original_cwd)

    def test_scan_depth2_gitignore_golden(self, test_repo_with_gitignore, capsys):
        """Test scan --depth 2 --respect-gitignore against golden file."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(test_repo_with_gitignore)

            # Mock sys.argv and run main
            import sys

            original_argv = sys.argv
            sys.argv = [
                "autorepro",
                "scan",
                "--json",
                "--depth",
                "2",
                "--respect-gitignore",
            ]

            exit_code = main()
            assert exit_code == 0

            captured = capsys.readouterr()
            actual = self._normalize_json_output(
                captured.out, str(test_repo_with_gitignore)
            )
            expected = self._load_golden_file("SCAN.depth2.gitignore.json")

            assert actual == expected

        finally:
            sys.argv = original_argv
            os.chdir(original_cwd)

    def test_scan_files_sample_behavior(self, test_repo, capsys):
        """Test that files_sample appears by default and respects --show."""
        import os

        original_cwd = os.getcwd()
        try:
            os.chdir(test_repo)

            # Test default behavior (should include files_sample)
            import sys

            original_argv = sys.argv
            sys.argv = ["autorepro", "scan", "--json", "--depth", "2"]

            exit_code = main()
            assert exit_code == 0

            captured = capsys.readouterr()
            result = json.loads(captured.out)

            # Should have files_sample for both languages
            assert "files_sample" in result["languages"]["python"]
            assert "files_sample" in result["languages"]["node"]

            # Test with --show 1 (should limit to 1 file per language)
            sys.argv = ["autorepro", "scan", "--json", "--depth", "2", "--show", "1"]

            exit_code = main()
            assert exit_code == 0

            captured = capsys.readouterr()
            result = json.loads(captured.out)

            # Should still have files_sample but limited to 1 file
            assert len(result["languages"]["python"]["files_sample"]) <= 1
            assert len(result["languages"]["node"]["files_sample"]) <= 1

        finally:
            sys.argv = original_argv
            os.chdir(original_cwd)
