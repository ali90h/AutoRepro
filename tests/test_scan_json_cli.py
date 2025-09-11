"""Tests for the scan CLI command with JSON functionality."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from autorepro.cli import main


class TestScanJsonCLI:
    """Test the scan CLI command with JSON functionality."""

    def _run_in_temp_dir(self, tmpdir_path, args):
        """Helper to run CLI command in a temporary directory."""
        original_cwd = os.getcwd()
        try:
            os.chdir(tmpdir_path)
            with patch("sys.argv", args):
                return main()
        finally:
            os.chdir(original_cwd)

    def test_scan_json_mixed_indices(self, capsys):
        """Test scan --json with mixed language indices."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create mixed indices
            (tmpdir_path / "pyproject.toml").write_text(
                "[build-system]"
            )  # Python config
            (tmpdir_path / "pnpm-lock.yaml").write_text(
                "lockfileVersion: 5.4"
            )  # Node lock
            (tmpdir_path / "main.py").write_text("print('hello')")  # Python source

            exit_code = self._run_in_temp_dir(
                tmpdir_path, ["autorepro", "scan", "--json"]
            )

            captured = capsys.readouterr()
            assert exit_code == 0

            # Parse JSON output
            json_output = json.loads(captured.out)

            # Validate schema
            assert "root" in json_output
            assert "detected" in json_output
            assert "languages" in json_output

            # Check root is absolute path (resolve both for comparison due to symlinks)
            assert Path(json_output["root"]).resolve() == tmpdir_path.resolve()

            # Check detected languages (should be alphabetical)
            assert json_output["detected"] == ["node", "python"]

            # Check languages data
            languages = json_output["languages"]
            assert "node" in languages
            assert "python" in languages

            # Node should have higher score due to lock file
            assert languages["node"]["score"] == 4
            assert languages["python"]["score"] == 4  # config(3) + source(1)

            # Validate reasons structure
            for data in languages.values():
                assert "score" in data
                assert "reasons" in data
                assert isinstance(data["reasons"], list)
                for reason in data["reasons"]:
                    assert "pattern" in reason
                    assert "path" in reason
                    assert "kind" in reason
                    assert "weight" in reason

    def test_scan_json_no_indices(self, capsys):
        """Test scan --json with empty directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            exit_code = self._run_in_temp_dir(
                tmpdir_path, ["autorepro", "scan", "--json"]
            )

            captured = capsys.readouterr()
            assert exit_code == 0

            # Parse JSON output
            json_output = json.loads(captured.out)

            # Should have empty results
            assert Path(json_output["root"]).resolve() == tmpdir_path.resolve()
            assert json_output["detected"] == []
            assert json_output["languages"] == {}

    def test_scan_show_scores_text_output(self, capsys):
        """Test --show-scores flag with text output (not JSON)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test file
            (tmpdir_path / "pyproject.toml").write_text("[build-system]")

            exit_code = self._run_in_temp_dir(
                tmpdir_path, ["autorepro", "scan", "--show-scores"]
            )

            captured = capsys.readouterr()
            assert exit_code == 0

            lines = captured.out.strip().splitlines()

            # Should have regular text output plus score
            assert "Detected: python" in lines[0]
            assert "- python -> pyproject.toml" in lines[1]
            assert "Score:" in lines[2]  # Score line should be present

    def test_scan_show_scores_ignored_with_json(self, capsys):
        """Test that --show-scores is ignored when --json is used."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test file
            (tmpdir_path / "pyproject.toml").write_text("[build-system]")

            exit_code = self._run_in_temp_dir(
                tmpdir_path, ["autorepro", "scan", "--json", "--show-scores"]
            )

            captured = capsys.readouterr()
            assert exit_code == 0

            # Should be valid JSON (--show-scores should not affect JSON output)
            json_output = json.loads(captured.out)
            assert "detected" in json_output
            assert "languages" in json_output

    def test_scan_json_preserves_alphabetical_order(self, capsys):
        """Test that JSON output preserves alphabetical order in detected array."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create files in non-alphabetical order
            (tmpdir_path / "Cargo.toml").write_text("[package]")  # rust
            (tmpdir_path / "main.py").write_text("print('hello')")  # python
            (tmpdir_path / "go.mod").write_text("module test")  # go

            exit_code = self._run_in_temp_dir(
                tmpdir_path, ["autorepro", "scan", "--json"]
            )

            captured = capsys.readouterr()
            assert exit_code == 0

            json_output = json.loads(captured.out)

            # Detected array should be alphabetical
            assert json_output["detected"] == ["go", "python", "rust"]

    def test_scan_json_java_detection(self, capsys):
        """Test Java detection with pom.xml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create Java config
            (tmpdir_path / "pom.xml").write_text("<project></project>")

            exit_code = self._run_in_temp_dir(
                tmpdir_path, ["autorepro", "scan", "--json"]
            )

            captured = capsys.readouterr()
            assert exit_code == 0

            json_output = json.loads(captured.out)

            assert json_output["detected"] == ["java"]
            assert json_output["languages"]["java"]["score"] == 3
            assert json_output["languages"]["java"]["reasons"][0]["kind"] == "config"

    def test_scan_json_rust_lockfile_and_config(self, capsys):
        """Test Rust detection with both Cargo.toml and Cargo.lock."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create Rust files
            (tmpdir_path / "Cargo.toml").write_text("[package]")
            (tmpdir_path / "Cargo.lock").write_text("[[package]]")

            exit_code = self._run_in_temp_dir(
                tmpdir_path, ["autorepro", "scan", "--json"]
            )

            captured = capsys.readouterr()
            assert exit_code == 0

            json_output = json.loads(captured.out)

            assert json_output["detected"] == ["rust"]
            # Cargo.toml (config: 3) + Cargo.lock (lock: 4) = 7
            assert json_output["languages"]["rust"]["score"] == 7

            reasons = json_output["languages"]["rust"]["reasons"]
            assert len(reasons) == 2
            kinds = [r["kind"] for r in reasons]
            assert "config" in kinds
            assert "lock" in kinds

    def test_scan_json_handles_io_errors(self, capsys):
        """Test that JSON output handles I/O errors gracefully."""
        with patch("sys.argv", ["autorepro", "scan", "--json"]):
            with patch("autorepro.cli.collect_evidence") as mock_collect:
                mock_collect.side_effect = OSError("Permission denied")
                exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 0

        # Should return valid JSON with empty results
        json_output = json.loads(captured.out)
        assert json_output["detected"] == []
        assert json_output["languages"] == {}

    def test_scan_default_behavior_unchanged(self, capsys):
        """Test that default scan behavior (no flags) remains unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create test file
            (tmpdir_path / "pyproject.toml").write_text("[build-system]")

            exit_code = self._run_in_temp_dir(tmpdir_path, ["autorepro", "scan"])

            captured = capsys.readouterr()
            assert exit_code == 0

            # Should use original text format
            lines = captured.out.strip().splitlines()
            assert len(lines) == 2
            assert "Detected: python" in lines[0]
            assert "- python -> pyproject.toml" in lines[1]

            # Should NOT have JSON format
            assert not captured.out.strip().startswith("{")

    def test_scan_json_multiple_node_files(self, capsys):
        """Test Node.js detection with multiple package manager files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create multiple Node files
            (tmpdir_path / "package.json").write_text('{"name": "test"}')
            (tmpdir_path / "yarn.lock").write_text("# yarn lock")

            exit_code = self._run_in_temp_dir(
                tmpdir_path, ["autorepro", "scan", "--json"]
            )

            captured = capsys.readouterr()
            assert exit_code == 0

            json_output = json.loads(captured.out)

            assert json_output["detected"] == ["node"]
            # package.json (config: 3) + yarn.lock (lock: 4) = 7
            assert json_output["languages"]["node"]["score"] == 7

    def test_scan_json_source_files_only(self, capsys):
        """Test detection with only source files (weight 1)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create only source files
            (tmpdir_path / "main.go").write_text("package main")
            (tmpdir_path / "utils.go").write_text("package main")

            exit_code = self._run_in_temp_dir(
                tmpdir_path, ["autorepro", "scan", "--json"]
            )

            captured = capsys.readouterr()
            assert exit_code == 0

            json_output = json.loads(captured.out)

            assert json_output["detected"] == ["go"]
            assert json_output["languages"]["go"]["score"] == 1  # source weight

            reasons = json_output["languages"]["go"]["reasons"]
            assert len(reasons) == 1
            assert reasons[0]["kind"] == "source"
            assert reasons[0]["pattern"] == "*.go"

    def test_scan_json_no_indicators_exit_zero(self, capsys):
        """Test scan --json with no indicators returns empty results and exit code 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create only non-language files
            (tmpdir_path / "README.md").write_text("# Project Documentation")
            (tmpdir_path / "LICENSE").write_text("MIT License")
            (tmpdir_path / "data.txt").write_text("Some data")

            exit_code = self._run_in_temp_dir(
                tmpdir_path, ["autorepro", "scan", "--json"]
            )

            captured = capsys.readouterr()
            assert exit_code == 0  # Should exit with success

            # Parse JSON output
            json_output = json.loads(captured.out)

            # Should have empty results
            assert json_output["detected"] == []
            assert json_output["languages"] == {}

            # Verify schema structure is still correct
            assert "root" in json_output
            assert "detected" in json_output
            assert "languages" in json_output
            assert Path(json_output["root"]).resolve() == tmpdir_path.resolve()
