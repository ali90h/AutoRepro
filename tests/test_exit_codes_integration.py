"""
Integration tests for CLI exit codes via subprocess.

Tests that main() returns:
- 0 on success (including scan with no languages detected)
- 2 on misuse (argparse errors, invalid arguments)
- 1 on I/O errors only
"""

import os
import subprocess
import sys


def run_autorepro_subprocess(args, cwd=None):
    """Run autorepro CLI via subprocess and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, "-m", "autorepro.cli"] + args
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=30)
    return result.returncode, result.stdout, result.stderr


class TestSuccessExitCodes:
    """Test that success operations return exit code 0."""

    def test_scan_with_languages_returns_zero(self, tmp_path):
        """Test that scan returns 0 when languages are detected."""
        # Create Python marker file
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[build-system]\nrequires = ["setuptools"]')

        returncode, stdout, stderr = run_autorepro_subprocess(["scan"], cwd=tmp_path)

        assert returncode == 0, (
            f"Expected exit code 0, got {returncode}. stderr: {stderr}"
        )
        assert "Detected: python" in stdout
        assert "python -> pyproject.toml" in stdout

    def test_scan_with_no_languages_returns_zero(self, tmp_path):
        """Test that scan returns 0 even when no languages are detected."""
        # Empty directory - no language markers
        returncode, stdout, stderr = run_autorepro_subprocess(["scan"], cwd=tmp_path)

        assert returncode == 0, (
            f"Expected exit code 0, got {returncode}. stderr: {stderr}"
        )
        assert "No known languages detected." in stdout

    def test_init_first_time_returns_zero(self, tmp_path):
        """Test that init returns 0 on successful creation."""
        returncode, stdout, stderr = run_autorepro_subprocess(["init"], cwd=tmp_path)

        assert returncode == 0, (
            f"Expected exit code 0, got {returncode}. stderr: {stderr}"
        )
        assert "Wrote devcontainer to" in stdout

        # Verify file was created
        devcontainer_file = tmp_path / ".devcontainer" / "devcontainer.json"
        assert devcontainer_file.exists()

    def test_init_already_exists_returns_zero(self, tmp_path):
        """Test that init returns 0 when file already exists (idempotent)."""
        # Create devcontainer first
        run_autorepro_subprocess(["init"], cwd=tmp_path)

        # Run again - should be idempotent success
        returncode, stdout, stderr = run_autorepro_subprocess(["init"], cwd=tmp_path)

        assert returncode == 0, (
            f"Expected exit code 0, got {returncode}. stderr: {stderr}"
        )
        assert "devcontainer.json already exists" in stdout
        assert "Use --force to overwrite" in stdout

    def test_plan_success_returns_zero(self, tmp_path):
        """Test that plan returns 0 on successful execution."""
        returncode, stdout, stderr = run_autorepro_subprocess(
            ["plan", "--desc", "test issue"], cwd=tmp_path
        )

        assert returncode == 0, (
            f"Expected exit code 0, got {returncode}. stderr: {stderr}"
        )
        assert "Wrote repro to" in stdout

        # Verify file was created
        repro_file = tmp_path / "repro.md"
        assert repro_file.exists()

    def test_plan_stdout_returns_zero(self, tmp_path):
        """Test that plan --out - returns 0."""
        returncode, stdout, stderr = run_autorepro_subprocess(
            ["plan", "--desc", "test issue", "--out", "-"], cwd=tmp_path
        )

        assert returncode == 0, (
            f"Expected exit code 0, got {returncode}. stderr: {stderr}"
        )
        assert "# Test Issue" in stdout  # Should contain markdown output

    def test_help_returns_zero(self, tmp_path):
        """Test that --help returns 0."""
        returncode, stdout, stderr = run_autorepro_subprocess(["--help"], cwd=tmp_path)

        assert returncode == 0, (
            f"Expected exit code 0, got {returncode}. stderr: {stderr}"
        )
        assert "CLI for AutoRepro" in stdout


class TestMisuseExitCodes:
    """Test that misuse/argparse errors return exit code 2."""

    def test_plan_missing_desc_returns_two(self, tmp_path):
        """Test that plan without --desc returns 2."""
        returncode, stdout, stderr = run_autorepro_subprocess(["plan"], cwd=tmp_path)

        assert returncode == 2, (
            f"Expected exit code 2, got {returncode}. stdout: {stdout}"
        )
        assert "one of the arguments --desc --file is required" in stderr

    def test_plan_desc_and_file_returns_two(self, tmp_path):
        """Test that plan with both --desc and --file returns 2."""
        # Create a temp file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        returncode, stdout, stderr = run_autorepro_subprocess(
            ["plan", "--desc", "test", "--file", str(test_file)], cwd=tmp_path
        )

        assert returncode == 2, (
            f"Expected exit code 2, got {returncode}. stdout: {stdout}"
        )
        assert "not allowed with argument" in stderr

    def test_invalid_command_returns_two(self, tmp_path):
        """Test that invalid command returns 2."""
        returncode, stdout, stderr = run_autorepro_subprocess(
            ["invalid_command"], cwd=tmp_path
        )

        assert returncode == 2, (
            f"Expected exit code 2, got {returncode}. stdout: {stdout}"
        )
        assert "invalid choice: 'invalid_command'" in stderr

    def test_invalid_repo_path_returns_two(self, tmp_path):
        """Test that --repo with non-existent path returns 2."""
        returncode, stdout, stderr = run_autorepro_subprocess(
            ["plan", "--desc", "test", "--repo", "/nonexistent/path"], cwd=tmp_path
        )

        assert returncode == 2, (
            f"Expected exit code 2, got {returncode}. stdout: {stdout}"
        )
        assert "does not exist or is not a directory" in stderr

    def test_out_points_to_directory_returns_two(self, tmp_path):
        """Test that --out pointing to directory returns 2."""
        # Create a directory instead of file
        out_dir = tmp_path / "output_dir"
        out_dir.mkdir()

        returncode, stdout, stderr = run_autorepro_subprocess(
            ["plan", "--desc", "test", "--out", str(out_dir)], cwd=tmp_path
        )

        assert returncode == 2, (
            f"Expected exit code 2, got {returncode}. stdout: {stdout}"
        )
        assert "Output path is a directory" in stdout

    def test_init_out_points_to_directory_returns_two(self, tmp_path):
        """Test that init --out pointing to directory returns 2."""
        # Create a directory instead of file
        out_dir = tmp_path / "output_dir"
        out_dir.mkdir()

        returncode, stdout, stderr = run_autorepro_subprocess(
            ["init", "--out", str(out_dir)], cwd=tmp_path
        )

        assert returncode == 2, (
            f"Expected exit code 2, got {returncode}. stdout: {stdout}"
        )
        assert "Output path is a directory" in stdout


class TestIOErrorExitCodes:
    """Test that I/O errors return exit code 1."""

    def test_plan_file_nonexistent_returns_one(self, tmp_path):
        """Test that --file pointing to non-existent file returns 1."""
        nonexistent_file = tmp_path / "nonexistent.txt"

        returncode, stdout, stderr = run_autorepro_subprocess(
            ["plan", "--file", str(nonexistent_file)], cwd=tmp_path
        )

        assert returncode == 1, (
            f"Expected exit code 1, got {returncode}. stdout: {stdout}"
        )
        assert f"Error reading file {nonexistent_file}" in stderr

    def test_plan_file_permission_denied_returns_one(self, tmp_path):
        """Test that --file with permission denied returns 1."""
        if os.name == "nt":  # Skip on Windows due to different permission model
            return

        # Create file and remove read permissions
        restricted_file = tmp_path / "restricted.txt"
        restricted_file.write_text("test content")
        restricted_file.chmod(0o000)  # No permissions

        try:
            returncode, stdout, stderr = run_autorepro_subprocess(
                ["plan", "--file", str(restricted_file)], cwd=tmp_path
            )

            assert returncode == 1, (
                f"Expected exit code 1, got {returncode}. stdout: {stdout}"
            )
            assert f"Error reading file {restricted_file}" in stderr
        finally:
            # Restore permissions for cleanup
            restricted_file.chmod(0o644)

    def test_write_permission_denied_returns_one(self, tmp_path):
        """Test that write permission error returns 1."""
        if os.name == "nt":  # Skip on Windows due to different permission model
            return

        # Create read-only directory
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)  # Read-only

        output_file = readonly_dir / "output.md"

        try:
            returncode, stdout, stderr = run_autorepro_subprocess(
                ["plan", "--desc", "test", "--out", str(output_file)], cwd=tmp_path
            )

            assert returncode == 1, (
                f"Expected exit code 1, got {returncode}. stdout: {stdout}"
            )
            assert f"Error writing file {output_file}" in stderr
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)
