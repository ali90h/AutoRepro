"""Tests for the AutoRepro CLI interface."""

import subprocess
import sys
from unittest.mock import patch

import pytest

from autorepro.cli import main


class TestCLIHelp:
    """Test CLI help functionality and exit codes."""

    def test_help_flag_short_returns_zero_exit_code(self):
        """Test that -h flag returns exit code 0."""
        with patch("sys.argv", ["autorepro", "-h"]):
            exit_code = main()
            assert exit_code == 0

    def test_help_flag_long_returns_zero_exit_code(self):
        """Test that --help flag returns exit code 0."""
        with patch("sys.argv", ["autorepro", "--help"]):
            exit_code = main()
            assert exit_code == 0

    def test_no_arguments_shows_help_and_returns_zero(self):
        """Test that calling without commands displays help and returns exit code 0."""
        with patch("sys.argv", ["autorepro"]):
            exit_code = main()
            assert exit_code == 0

    @pytest.mark.parametrize("help_flag", ["-h", "--help"])
    def test_help_output_contains_program_info(self, help_flag, capsys):
        """Test that help output contains program name and description."""
        with patch("sys.argv", ["autorepro", help_flag]):
            try:
                main()
            except SystemExit:
                pass  # argparse calls sys.exit for help, which is expected

        captured = capsys.readouterr()
        help_output = captured.out + captured.err

        # Check for program name
        assert "autorepro" in help_output.lower()
        # Check for description keywords
        assert any(
            keyword in help_output.lower()
            for keyword in ["autorepro", "repro", "issue", "workspace", "cli"]
        )

    def test_no_args_help_output_contains_program_info(self, capsys):
        """Test that no-args help output contains program name and description."""
        with patch("sys.argv", ["autorepro"]):
            exit_code = main()
            assert exit_code == 0

        captured = capsys.readouterr()
        help_output = captured.out + captured.err

        # Check for program name
        assert "autorepro" in help_output.lower()
        # Check for description keywords
        assert any(
            keyword in help_output.lower()
            for keyword in ["autorepro", "repro", "issue", "workspace", "cli"]
        )


class TestCLIIntegration:
    """Integration tests using subprocess to test the actual CLI command."""

    def test_cli_help_via_subprocess(self):
        """Test CLI help using subprocess to simulate real usage."""
        # Test -h flag
        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "-h"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert (
            "autorepro" in result.stdout.lower() or "autorepro" in result.stderr.lower()
        )

        # Test --help flag
        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert (
            "autorepro" in result.stdout.lower() or "autorepro" in result.stderr.lower()
        )

    def test_cli_no_args_via_subprocess(self):
        """Test CLI without arguments using subprocess."""
        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli"], capture_output=True, text=True
        )
        assert result.returncode == 0
        assert (
            "autorepro" in result.stdout.lower() or "autorepro" in result.stderr.lower()
        )

    def test_cli_version_via_subprocess(self):
        """Test CLI version flag using subprocess."""
        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "--version"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "0.0.1" in result.stdout or "0.0.1" in result.stderr


class TestCLIErrorHandling:
    """Test CLI error handling and edge cases."""

    def test_unknown_option_returns_exit_code_2(self):
        """Test that unknown options return exit code 2 and show error message."""
        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "--unknown-option"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        error_output = result.stdout + result.stderr
        assert "unrecognized arguments" in error_output.lower()

    def test_invalid_short_option_returns_exit_code_2(self):
        """Test that invalid short options return exit code 2."""
        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "-x"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        error_output = result.stdout + result.stderr
        assert "unrecognized arguments" in error_output.lower()

    def test_multiple_unknown_args_returns_exit_code_2(self):
        """Test that multiple unknown arguments return exit code 2."""
        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "unknown", "args"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        error_output = result.stdout + result.stderr
        assert "unrecognized arguments" in error_output.lower()
