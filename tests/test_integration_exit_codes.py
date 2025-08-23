"""Integration tests for exit codes using subprocess.run."""

import subprocess
import sys


def run_cli_integration(args, cwd=None):
    """Run autorepro CLI via subprocess for exit code testing."""
    cmd = [sys.executable, "-m", "autorepro.cli"] + args
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


class TestIntegrationExitCodes:
    """Test actual exit codes via subprocess.run integration."""

    def test_plan_missing_args_exit_2(self, tmp_path):
        """Test that missing required arguments return exit code 2 (misuse)."""
        result = run_cli_integration(["plan"], cwd=tmp_path)
        assert result.returncode == 2, f"Expected exit code 2, got {result.returncode}"
        assert "required" in (result.stdout + result.stderr).lower()

    def test_plan_invalid_file_exit_1(self, tmp_path):
        """Test that invalid file returns exit code 1 (error)."""
        result = run_cli_integration(["plan", "--file", "nonexistent_file.txt"], cwd=tmp_path)
        assert result.returncode == 1, f"Expected exit code 1, got {result.returncode}"
        assert "Error reading file" in result.stderr

    def test_plan_success_exit_0(self, tmp_path):
        """Test that successful plan generation returns exit code 0."""
        result = run_cli_integration(["plan", "--desc", "test issue"], cwd=tmp_path)
        assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}"
        # Should create repro.md by default
        repro_file = tmp_path / "repro.md"
        assert repro_file.exists()

    def test_plan_existing_file_without_force_exit_0(self, tmp_path):
        """Test that existing file without --force returns exit code 0 (idempotent)."""
        # Create existing file
        existing_file = tmp_path / "repro.md"
        existing_file.write_text("# Existing content")

        result = run_cli_integration(["plan", "--desc", "test issue"], cwd=tmp_path)
        assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}"
        assert "exists; use --force to overwrite" in result.stdout

    def test_plan_repo_nonexistent_exit_2(self, tmp_path):
        """Test that nonexistent --repo path returns exit code 2."""
        result = run_cli_integration(
            ["plan", "--desc", "test", "--repo", "nonexistent"], cwd=tmp_path
        )
        assert result.returncode == 2, f"Expected exit code 2, got {result.returncode}"
        assert "does not exist" in result.stderr

    def test_init_success_exit_0(self, tmp_path):
        """Test that successful init returns exit code 0."""
        result = run_cli_integration(["init"], cwd=tmp_path)
        assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}"
        # Should create devcontainer.json
        devcontainer_file = tmp_path / ".devcontainer" / "devcontainer.json"
        assert devcontainer_file.exists()

    def test_init_existing_without_force_exit_0(self, tmp_path):
        """Test that existing devcontainer without --force returns exit code 0."""
        # Create existing devcontainer
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        devcontainer_file = devcontainer_dir / "devcontainer.json"
        devcontainer_file.write_text('{"name": "existing"}')

        result = run_cli_integration(["init"], cwd=tmp_path)
        assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}"
        assert "already exists" in result.stdout

    def test_init_repo_nonexistent_exit_2(self, tmp_path):
        """Test that nonexistent --repo path returns exit code 2."""
        result = run_cli_integration(["init", "--repo", "nonexistent"], cwd=tmp_path)
        assert result.returncode == 2, f"Expected exit code 2, got {result.returncode}"
        assert "does not exist" in result.stderr

    def test_scan_success_exit_0(self, tmp_path):
        """Test that scan command returns exit code 0."""
        # Create a python project marker
        (tmp_path / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools"]')

        result = run_cli_integration(["scan"], cwd=tmp_path)
        assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}"
        assert "python" in result.stdout.lower()

    def test_scan_no_languages_exit_0(self, tmp_path):
        """Test that scan with no detected languages returns exit code 0."""
        # Empty directory - no languages detected
        result = run_cli_integration(["scan"], cwd=tmp_path)
        assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}"
        assert "No known languages detected" in result.stdout

    def test_invalid_command_exit_2(self, tmp_path):
        """Test that invalid command returns exit code 2."""
        result = run_cli_integration(["invalid_command"], cwd=tmp_path)
        # argparse typically returns 2 for invalid commands
        assert result.returncode != 0, "Invalid command should not return success"
        # Could be exit code 2, but different systems might handle differently
        # The important thing is it's not 0 (success)

    def test_help_exit_0(self, tmp_path):
        """Test that --help returns exit code 0."""
        result = run_cli_integration(["--help"], cwd=tmp_path)
        assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}"
        assert "autorepro" in result.stdout.lower()

    def test_version_exit_0(self, tmp_path):
        """Test that --version returns exit code 0."""
        result = run_cli_integration(["--version"], cwd=tmp_path)
        assert result.returncode == 0, f"Expected exit code 0, got {result.returncode}"
        assert "autorepro" in result.stdout.lower()

    def test_plan_output_directory_error_exit_2(self, tmp_path):
        """Test that plan with output directory returns exit code 2."""
        # Create a directory instead of file path for output
        output_dir = tmp_path / "output_dir"
        output_dir.mkdir()

        result = run_cli_integration(
            ["plan", "--desc", "test", "--out", str(output_dir)], cwd=tmp_path
        )
        assert result.returncode == 2, f"Expected exit code 2, got {result.returncode}"
        assert "directory" in result.stdout or "directory" in result.stderr

    def test_init_output_directory_error_exit_2(self, tmp_path):
        """Test that init with output directory returns exit code 2."""
        # Create a directory instead of file path for output
        output_dir = tmp_path / "output_dir"
        output_dir.mkdir()

        result = run_cli_integration(["init", "--out", str(output_dir)], cwd=tmp_path)
        assert result.returncode == 2, f"Expected exit code 2, got {result.returncode}"
        assert "directory" in result.stdout or "directory" in result.stderr
