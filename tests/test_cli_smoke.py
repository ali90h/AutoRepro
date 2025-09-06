"""
CLI smoke tests for AutoRepro commands.

These tests verify that basic CLI commands work without errors and produce
expected output. They use subprocess to test the actual CLI interface.
"""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.smoke
class TestCLISmokeBasic:
    """Basic CLI smoke tests for core functionality."""

    @pytest.fixture
    def python_cmd(self):
        """Get Python command for subprocess calls."""
        return [sys.executable, "-m", "autorepro"]

    def test_help_command_smoke(self, python_cmd):
        """Test that --help command works without errors."""
        result = subprocess.run(
            python_cmd + ["--help"], capture_output=True, text=True, check=False, timeout=10
        )

        assert result.returncode == 0
        assert "autorepro" in result.stdout.lower()
        assert "usage:" in result.stdout.lower()
        assert len(result.stdout) > 100  # Ensure substantial help content

    def test_version_command_smoke(self, python_cmd):
        """Test that --version command works without errors."""
        result = subprocess.run(
            python_cmd + ["--version"], capture_output=True, text=True, check=False, timeout=10
        )

        assert result.returncode == 0
        # Version output should contain program name and version
        output = result.stdout + result.stderr
        assert "autorepro" in output.lower()
        # Should contain version number (digit.digit format)
        assert any(char.isdigit() for char in output)

    def test_no_command_shows_help_smoke(self, python_cmd):
        """Test that calling without commands displays help."""
        result = subprocess.run(python_cmd, capture_output=True, text=True, check=False, timeout=10)

        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
        assert "available commands" in result.stdout.lower() or "commands:" in result.stdout.lower()


@pytest.mark.smoke
class TestCLISmokeSubcommands:
    """Smoke tests for individual subcommands."""

    @pytest.fixture
    def python_cmd(self):
        """Get Python command for subprocess calls."""
        return [sys.executable, "-m", "autorepro"]

    def test_scan_help_smoke(self, python_cmd):
        """Test scan --help command works."""
        result = subprocess.run(
            python_cmd + ["scan", "--help"], capture_output=True, text=True, check=False, timeout=10
        )

        assert result.returncode == 0
        assert "scan" in result.stdout.lower()
        assert "language" in result.stdout.lower() or "framework" in result.stdout.lower()

    def test_scan_json_flag_smoke(self, python_cmd, tmp_path):
        """Test scan command with --json flag."""
        # Change to temp directory to avoid side effects
        original_cwd = Path.cwd()
        try:
            import os

            os.chdir(tmp_path)

            result = subprocess.run(
                python_cmd + ["scan", "--json"],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )

            # Should succeed even in empty directory
            assert result.returncode == 0
            # Output should be valid JSON
            import json

            try:
                json_output = json.loads(result.stdout)
                assert isinstance(json_output, dict)
                assert "detected" in json_output or "languages" in json_output
            except json.JSONDecodeError:
                pytest.fail(f"Expected JSON output but got: {result.stdout}")

        finally:
            os.chdir(original_cwd)

    def test_plan_help_smoke(self, python_cmd):
        """Test plan --help command works."""
        result = subprocess.run(
            python_cmd + ["plan", "--help"], capture_output=True, text=True, check=False, timeout=10
        )

        assert result.returncode == 0
        assert "plan" in result.stdout.lower()
        assert "desc" in result.stdout.lower() or "description" in result.stdout.lower()

    def test_plan_dry_run_smoke(self, python_cmd):
        """Test plan command with --dry-run flag."""
        result = subprocess.run(
            python_cmd + ["plan", "--desc", "test issue", "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )

        assert result.returncode == 0
        assert len(result.stdout) > 0  # Should produce output
        # Dry run should not create files
        assert "assumptions" in result.stdout.lower() or "commands" in result.stdout.lower()

    def test_init_help_smoke(self, python_cmd):
        """Test init --help command works."""
        result = subprocess.run(
            python_cmd + ["init", "--help"], capture_output=True, text=True, check=False, timeout=10
        )

        assert result.returncode == 0
        assert "init" in result.stdout.lower()
        assert "devcontainer" in result.stdout.lower()

    def test_init_dry_run_smoke(self, python_cmd):
        """Test init command with --dry-run flag."""
        result = subprocess.run(
            python_cmd + ["init", "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )

        assert result.returncode == 0
        assert len(result.stdout) > 0  # Should produce JSON output
        # Should be valid JSON
        import json

        try:
            json_output = json.loads(result.stdout)
            assert isinstance(json_output, dict)
            assert "name" in json_output  # Devcontainer should have name
        except json.JSONDecodeError:
            pytest.fail(f"Expected JSON output but got: {result.stdout}")

    def test_exec_help_smoke(self, python_cmd):
        """Test exec --help command works."""
        result = subprocess.run(
            python_cmd + ["exec", "--help"], capture_output=True, text=True, check=False, timeout=10
        )

        assert result.returncode == 0
        assert "exec" in result.stdout.lower()
        assert "command" in result.stdout.lower()

    def test_pr_help_smoke(self, python_cmd):
        """Test pr --help command works."""
        result = subprocess.run(
            python_cmd + ["pr", "--help"], capture_output=True, text=True, check=False, timeout=10
        )

        assert result.returncode == 0
        assert "pr" in result.stdout.lower()
        assert "draft pr" in result.stdout.lower() or "repo-slug" in result.stdout.lower()


@pytest.mark.smoke
class TestCLISmokeComplexCommands:
    """Smoke tests for complex command combinations."""

    @pytest.fixture
    def python_cmd(self):
        """Get Python command for subprocess calls."""
        return [sys.executable, "-m", "autorepro"]

    def test_plan_json_format_smoke(self, python_cmd):
        """Test plan command with --format json."""
        result = subprocess.run(
            python_cmd + ["plan", "--desc", "test issue", "--format", "json", "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )

        assert result.returncode == 0
        # Should produce valid JSON
        import json

        try:
            json_output = json.loads(result.stdout)
            assert isinstance(json_output, dict)
            assert "title" in json_output or "assumptions" in json_output
        except json.JSONDecodeError:
            pytest.fail(f"Expected JSON output but got: {result.stdout}")

    def test_plan_strict_mode_smoke(self, python_cmd):
        """Test plan command with --strict flag."""
        result = subprocess.run(
            python_cmd + ["plan", "--desc", "test issue", "--strict", "--dry-run"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )

        # Strict mode may fail (exit code 1) if no commands meet criteria
        # or succeed (exit code 0) - both are valid
        assert result.returncode in [0, 1]

        if result.returncode == 1:
            # Should have error message about min-score
            error_output = result.stderr.lower()
            assert "min-score" in error_output or "no candidate" in error_output

    def test_scan_with_multiple_flags_smoke(self, python_cmd, tmp_path):
        """Test scan command with multiple flags."""
        original_cwd = Path.cwd()
        try:
            import os

            os.chdir(tmp_path)

            result = subprocess.run(
                python_cmd + ["scan", "--json", "--show-scores"],
                capture_output=True,
                text=True,
                check=False,
                timeout=15,
            )

            assert result.returncode == 0
            # Should produce JSON output (--json takes precedence)
            import json

            try:
                json_output = json.loads(result.stdout)
                assert isinstance(json_output, dict)
            except json.JSONDecodeError:
                pytest.fail(f"Expected JSON output but got: {result.stdout}")

        finally:
            os.chdir(original_cwd)


@pytest.mark.smoke
class TestCLISmokeErrorHandling:
    """Smoke tests for error conditions and edge cases."""

    @pytest.fixture
    def python_cmd(self):
        """Get Python command for subprocess calls."""
        return [sys.executable, "-m", "autorepro"]

    def test_invalid_command_smoke(self, python_cmd):
        """Test that invalid commands produce appropriate errors."""
        result = subprocess.run(
            python_cmd + ["invalid-command"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )

        # Should show error and help
        assert result.returncode == 2  # argparse error code
        error_output = result.stderr.lower()
        assert "invalid choice" in error_output or "unknown" in error_output

    def test_plan_missing_required_args_smoke(self, python_cmd):
        """Test plan command with missing required arguments."""
        result = subprocess.run(
            python_cmd + ["plan"], capture_output=True, text=True, check=False, timeout=10
        )

        # Should fail with error about required arguments
        assert result.returncode == 2  # argparse error code
        error_output = result.stderr.lower()
        assert "required" in error_output or "desc" in error_output or "file" in error_output

    def test_exec_missing_required_args_smoke(self, python_cmd):
        """Test exec command with missing required arguments."""
        result = subprocess.run(
            python_cmd + ["exec"], capture_output=True, text=True, check=False, timeout=10
        )

        # Should fail with error about required arguments
        assert result.returncode == 2  # argparse error code
        error_output = result.stderr.lower()
        assert "required" in error_output or "desc" in error_output or "file" in error_output

    def test_pr_missing_required_args_smoke(self, python_cmd):
        """Test pr command with missing required arguments."""
        result = subprocess.run(
            python_cmd + ["pr"], capture_output=True, text=True, check=False, timeout=10
        )

        # Should fail with error about required arguments
        assert result.returncode == 2  # argparse error code
        error_output = result.stderr.lower()
        assert "required" in error_output


@pytest.mark.smoke
class TestCLISmokePerformance:
    """Basic performance smoke tests to ensure commands don't hang."""

    @pytest.fixture
    def python_cmd(self):
        """Get Python command for subprocess calls."""
        return [sys.executable, "-m", "autorepro"]

    @pytest.mark.timeout(30)  # Ensure tests don't hang
    def test_all_help_commands_fast(self, python_cmd):
        """Test that all help commands complete quickly."""
        commands = [
            "--help",
            "scan --help",
            "init --help",
            "plan --help",
            "exec --help",
            "pr --help",
        ]

        for cmd in commands:
            cmd_args = cmd.split()
            result = subprocess.run(
                python_cmd + cmd_args, capture_output=True, text=True, check=False, timeout=10
            )
            assert result.returncode == 0, (
                f"Command '{cmd}' failed with exit code {result.returncode}"
            )

    @pytest.mark.timeout(30)
    def test_dry_run_commands_fast(self, python_cmd):
        """Test that dry-run commands complete quickly."""
        commands = [
            ["plan", "--desc", "test", "--dry-run"],
            ["init", "--dry-run"],
            ["scan", "--json"],
        ]

        for cmd_args in commands:
            result = subprocess.run(
                python_cmd + cmd_args, capture_output=True, text=True, check=False, timeout=15
            )
            assert result.returncode == 0, (
                f"Command {cmd_args} failed with exit code {result.returncode}"
            )
