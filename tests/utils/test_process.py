"""
Tests for autorepro.utils.process module.

These tests validate the process execution utilities that replace duplicate
subprocess patterns found across the AutoRepro codebase.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from autorepro.utils.process import (
    ProcessResult,
    ProcessRunner,
    SubprocessConfig,
    safe_subprocess_run,
)


class TestProcessResult:
    """Test ProcessResult data class."""

    def test_process_result_initialization(self):
        """Test ProcessResult initializes with correct attributes."""
        result = ProcessResult(exit_code=0, stdout="output", stderr="error", cmd=["echo", "hello"])

        assert result.exit_code == 0
        assert result.stdout == "output"
        assert result.stderr == "error"
        assert result.cmd == ["echo", "hello"]

    def test_success_property_true_for_zero_exit(self):
        """Test success property returns True for exit code 0."""
        result = ProcessResult(0, "", "", ["cmd"])
        assert result.success is True

    def test_success_property_false_for_nonzero_exit(self):
        """Test success property returns False for non-zero exit code."""
        result = ProcessResult(1, "", "", ["cmd"])
        assert result.success is False

    def test_cmd_str_property_joins_command(self):
        """Test cmd_str property joins command list with spaces."""
        result = ProcessResult(0, "", "", ["git", "status", "--porcelain"])
        assert result.cmd_str == "git status --porcelain"


class TestProcessRunner:
    """Test ProcessRunner utility class."""

    @patch("subprocess.run")
    def test_run_with_capture_successful_command(self, mock_run):
        """Test run_with_capture handles successful command execution."""
        mock_completed = MagicMock()
        mock_completed.returncode = 0
        mock_completed.stdout = "success output"
        mock_completed.stderr = ""
        mock_run.return_value = mock_completed

        result = ProcessRunner.run_with_capture(["echo", "hello"])

        assert result.success is True
        assert result.exit_code == 0
        assert result.stdout == "success output"
        assert result.stderr == ""
        assert result.cmd == ["echo", "hello"]

    @patch("subprocess.run")
    def test_run_with_capture_failed_command(self, mock_run):
        """Test run_with_capture handles failed command execution."""
        mock_completed = MagicMock()
        mock_completed.returncode = 1
        mock_completed.stdout = ""
        mock_completed.stderr = "error output"
        mock_run.return_value = mock_completed

        result = ProcessRunner.run_with_capture(["false"])

        assert result.success is False
        assert result.exit_code == 1
        assert result.stdout == ""
        assert result.stderr == "error output"

    @patch("subprocess.run")
    def test_run_with_capture_timeout_handling(self, mock_run):
        """Test run_with_capture handles timeout correctly."""
        timeout_exc = subprocess.TimeoutExpired(["sleep", "10"], 5)
        timeout_exc.stdout = ""
        timeout_exc.stderr = ""
        mock_run.side_effect = timeout_exc

        result = ProcessRunner.run_with_capture(["sleep", "10"], timeout=5)

        assert result.exit_code == 124  # Standard timeout exit code
        assert "timed out after 5 seconds" in result.stderr
        assert result.stdout == ""

    @patch("subprocess.run")
    def test_run_with_capture_command_not_found(self, mock_run):
        """Test run_with_capture handles FileNotFoundError."""
        mock_run.side_effect = FileNotFoundError("Command not found")

        result = ProcessRunner.run_with_capture(["nonexistent-command"])

        assert result.exit_code == 127  # Standard "command not found" exit code
        assert "Command not found: nonexistent-command" in result.stderr
        assert result.stdout == ""

    @patch("subprocess.run")
    def test_run_with_capture_os_error(self, mock_run):
        """Test run_with_capture handles OSError."""
        mock_run.side_effect = OSError("Permission denied")

        result = ProcessRunner.run_with_capture(["restricted-command"])

        assert result.exit_code == 1
        assert "Failed to execute command: Permission denied" in result.stderr
        assert result.stdout == ""

    def test_run_with_capture_string_command_conversion(self):
        """Test run_with_capture converts string commands to list."""
        with patch("subprocess.run") as mock_run:
            mock_completed = MagicMock()
            mock_completed.returncode = 0
            mock_completed.stdout = "output"
            mock_completed.stderr = ""
            mock_run.return_value = mock_completed

            ProcessRunner.run_with_capture("echo hello world")

            # Verify command was split properly
            mock_run.assert_called_once()
            args, kwargs = mock_run.call_args
            assert args[0] == ["echo", "hello", "world"]

    @patch("subprocess.run")
    def test_run_with_capture_passes_parameters_correctly(self, mock_run):
        """Test run_with_capture passes all parameters to subprocess.run."""
        mock_completed = MagicMock()
        mock_completed.returncode = 0
        mock_completed.stdout = ""
        mock_completed.stderr = ""
        mock_run.return_value = mock_completed

        env_vars = {"TEST_VAR": "test_value"}
        cwd_path = Path("/test/dir")

        ProcessRunner.run_with_capture(
            ["test-cmd"], cwd=cwd_path, env=env_vars, timeout=30, check=True
        )

        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert kwargs["cwd"] == str(cwd_path)
        assert kwargs["env"] == env_vars
        assert kwargs["timeout"] == 30
        assert kwargs["check"] is True
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True

    @patch("autorepro.utils.process.ProcessRunner.run_with_capture")
    def test_run_git_command_prepends_git(self, mock_run_with_capture):
        """Test run_git_command prepends 'git' to command."""
        mock_run_with_capture.return_value = ProcessResult(0, "", "", ["git", "status"])

        ProcessRunner.run_git_command(["status", "--porcelain"])

        mock_run_with_capture.assert_called_once_with(
            ["git", "status", "--porcelain"], cwd=None, check=True
        )

    @patch("autorepro.utils.process.ProcessRunner.run_with_capture")
    def test_run_git_command_passes_parameters(self, mock_run_with_capture):
        """Test run_git_command passes cwd and check parameters."""
        mock_run_with_capture.return_value = ProcessResult(0, "", "", ["git", "log"])
        cwd_path = Path("/repo")

        ProcessRunner.run_git_command(["log", "--oneline"], cwd=cwd_path, check=False)

        mock_run_with_capture.assert_called_once_with(
            ["git", "log", "--oneline"], cwd=cwd_path, check=False
        )

    @patch("autorepro.utils.process.ProcessRunner.run_with_capture")
    def test_run_gh_command_uses_custom_gh_path(self, mock_run_with_capture):
        """Test run_gh_command uses custom gh executable path."""
        mock_run_with_capture.return_value = ProcessResult(0, "", "", ["custom-gh", "pr", "list"])

        ProcessRunner.run_gh_command(["pr", "list"], gh_path="custom-gh")

        mock_run_with_capture.assert_called_once_with(
            ["custom-gh", "pr", "list"], cwd=None, check=True
        )

    @patch("autorepro.utils.process.ProcessRunner.run_with_capture")
    def test_run_python_command_uses_custom_executable(self, mock_run_with_capture):
        """Test run_python_command uses custom Python executable."""
        mock_run_with_capture.return_value = ProcessResult(
            0, "", "", ["python3.9", "-c", "print('hello')"]
        )

        ProcessRunner.run_python_command(["-c", "print('hello')"], python_executable="python3.9")

        mock_run_with_capture.assert_called_once_with(
            ["python3.9", "-c", "print('hello')"], cwd=None, env=None, timeout=None
        )

    def test_run_with_capture_integration_real_command(self):
        """Integration test with real command execution."""
        # Use a simple, cross-platform command
        result = ProcessRunner.run_with_capture(["echo", "integration test"])

        assert result.success is True
        assert result.exit_code == 0
        assert "integration test" in result.stdout
        assert result.cmd == ["echo", "integration test"]


class TestSafeSubprocessRun:
    """Test safe_subprocess_run utility function."""

    @patch("subprocess.run")
    def test_safe_subprocess_run_forwards_parameters(self, mock_run):
        """Test safe_subprocess_run forwards all parameters correctly."""
        mock_completed = MagicMock()
        mock_run.return_value = mock_completed

        env_vars = {"TEST": "value"}
        cwd_path = Path("/test")

        config = SubprocessConfig(
            cmd=["test-cmd", "arg"],
            cwd=cwd_path,
            env=env_vars,
            timeout=60,
            capture_output=False,
            text=False,
            check=True,
        )
        safe_subprocess_run(config)

        mock_run.assert_called_once_with(
            ["test-cmd", "arg"],
            cwd=str(cwd_path),
            env=env_vars,
            timeout=60,
            capture_output=False,
            text=False,
            check=True,
        )

    def test_safe_subprocess_run_string_command_conversion(self):
        """Test safe_subprocess_run converts string commands to list."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock()

            config = SubprocessConfig(cmd="echo hello world")
            safe_subprocess_run(config)

            args, kwargs = mock_run.call_args
            assert args[0] == ["echo", "hello", "world"]

    def test_safe_subprocess_run_integration_real_command(self):
        """Integration test with real command execution."""
        config = SubprocessConfig(cmd=["echo", "safe test"], capture_output=True, text=True)
        result = safe_subprocess_run(config)

        assert result.returncode == 0
        assert "safe test" in result.stdout
