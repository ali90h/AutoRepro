"""Tests for the scan CLI command."""

import tempfile
from unittest.mock import patch

from autorepro.cli import main


class TestScanCLI:
    """Test the scan CLI command."""

    def test_scan_empty_directory(self, capsys):
        """Test scan command in empty directory."""
        with tempfile.TemporaryDirectory():
            with patch("autorepro.cli.detect_languages") as mock_detect:
                mock_detect.return_value = []

                with patch("sys.argv", ["autorepro", "scan"]):
                    exit_code = main()

                captured = capsys.readouterr()
                assert exit_code == 0
                assert captured.out.strip() == "No known languages detected."
                mock_detect.assert_called_once_with(".")

    def test_scan_single_language(self, capsys):
        """Test scan command with single language detected."""
        with patch("autorepro.cli.detect_languages") as mock_detect:
            mock_detect.return_value = [("python", ["pyproject.toml"])]

            with patch("sys.argv", ["autorepro", "scan"]):
                exit_code = main()

            captured = capsys.readouterr()
            assert exit_code == 0
            lines = [line.strip() for line in captured.out.strip().splitlines()]
            assert len(lines) == 2
            assert lines[0] == "Detected: python"
            assert lines[1] == "- python -> pyproject.toml"

    def test_scan_multiple_languages(self, capsys):
        """Test scan command with multiple languages detected."""
        with patch("autorepro.cli.detect_languages") as mock_detect:
            mock_detect.return_value = [
                ("go", ["go.mod"]),
                ("node", ["package.json", "pnpm-lock.yaml"]),
                ("python", ["pyproject.toml"]),
            ]

            with patch("sys.argv", ["autorepro", "scan"]):
                exit_code = main()

            captured = capsys.readouterr()
            assert exit_code == 0
            lines = [line.strip() for line in captured.out.strip().splitlines()]
            assert len(lines) == 4
            assert lines[0] == "Detected: go, node, python"
            assert lines[1] == "- go -> go.mod"
            assert lines[2] == "- node -> package.json, pnpm-lock.yaml"
            assert lines[3] == "- python -> pyproject.toml"

    def test_scan_with_multiple_reasons(self, capsys):
        """Test scan command with multiple reasons for a language."""
        with patch("autorepro.cli.detect_languages") as mock_detect:
            mock_detect.return_value = [
                ("python", ["pyproject.toml", "requirements.txt", "setup.py"])
            ]

            with patch("sys.argv", ["autorepro", "scan"]):
                exit_code = main()

            captured = capsys.readouterr()
            assert exit_code == 0
            lines = [line.strip() for line in captured.out.strip().splitlines()]
            assert len(lines) == 2
            assert lines[0] == "Detected: python"
            assert lines[1] == "- python -> pyproject.toml, requirements.txt, setup.py"

    def test_scan_help(self, capsys):
        """Test scan help command."""
        with patch("sys.argv", ["autorepro", "scan", "--help"]):
            exit_code = main()

            # argparse exits with 0 for help
            assert exit_code == 0

            captured = capsys.readouterr()
            help_output = captured.out + captured.err
            assert "usage:" in help_output.lower()
            assert "scan" in help_output.lower()

    def test_no_command_shows_help(self, capsys):
        """Test that no command shows help."""
        with patch("sys.argv", ["autorepro"]):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 0
        assert "autorepro" in captured.out
        assert "scan" in captured.out

    def test_invalid_command_returns_exit_code_2(self, capsys):
        """Test that invalid command returns exit code 2."""
        with patch("sys.argv", ["autorepro", "invalid"]):
            exit_code = main()

        captured = capsys.readouterr()
        assert exit_code == 2
        error_output = captured.out + captured.err
        assert "invalid choice" in error_output.lower()
