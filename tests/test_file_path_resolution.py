"""Test file path resolution for --file option with --repo.

Tests the unified rule:
1. Paths in --file are interpreted relative to CWD first
2. If CWD fails and --repo is specified, try Path(repo)/file as fallback
3. Absolute paths are used as-is
"""

from tests.test_utils import run_autorepro_subprocess


def run_plan_subprocess(args, cwd=None):
    """Run autorepro plan via subprocess."""
    return run_autorepro_subprocess(["plan"] + args, cwd=cwd)


class TestFilePathResolution:
    """Test file path resolution behavior with --file and --repo."""

    def test_file_relative_to_cwd_success(self, tmp_path):
        """Test that relative file paths work from CWD (primary behavior)."""
        # Create file in current directory
        issue_file = tmp_path / "issue.txt"
        issue_file.write_text("pytest failing on CI")

        # Create separate repo directory
        repo_dir = tmp_path / "project"
        repo_dir.mkdir()
        (repo_dir / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools"]')

        # Run from tmp_path, file should be found relative to CWD
        result = run_plan_subprocess(
            ["--file", "issue.txt", "--repo", str(repo_dir), "--dry-run"], cwd=tmp_path
        )

        assert result.returncode == 0, (
            f"Expected success, got {result.returncode}. stderr: {result.stderr}"
        )
        assert "# Pytest Failing On Ci" in result.stdout
        assert "pytest" in result.stdout  # Should suggest pytest commands

    def test_file_fallback_to_repo_success(self, tmp_path):
        """Test that file falls back to repo directory when not found in CWD."""
        # Create repo directory with issue file
        repo_dir = tmp_path / "project"
        repo_dir.mkdir()
        (repo_dir / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools"]')
        issue_file = repo_dir / "issue.txt"
        issue_file.write_text("go test timeout")

        # Create different working directory (without the issue file)
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        # Run from work_dir, file should NOT be found in CWD but SHOULD fallback to repo
        result = run_plan_subprocess(
            ["--file", "issue.txt", "--repo", str(repo_dir), "--dry-run"], cwd=work_dir
        )

        assert result.returncode == 0, (
            f"Expected success, got {result.returncode}. stderr: {result.stderr}"
        )
        assert "# Go Test Timeout" in result.stdout
        assert "go test" in result.stdout  # Should suggest go test commands

    def test_file_cwd_takes_precedence_over_repo(self, tmp_path):
        """Test that CWD file takes precedence over repo file when both exist."""
        # Create repo directory with issue file
        repo_dir = tmp_path / "project"
        repo_dir.mkdir()
        (repo_dir / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools"]')
        repo_issue = repo_dir / "issue.txt"
        repo_issue.write_text("repo file content - go test")

        # Create working directory with different issue file (same name)
        work_dir = tmp_path / "work"
        work_dir.mkdir()
        cwd_issue = work_dir / "issue.txt"
        cwd_issue.write_text("cwd file content - pytest failing")

        # Run from work_dir - should use CWD file, not repo file
        result = run_plan_subprocess(
            ["--file", "issue.txt", "--repo", str(repo_dir), "--dry-run"], cwd=work_dir
        )

        assert result.returncode == 0, (
            f"Expected success, got {result.returncode}. stderr: {result.stderr}"
        )
        assert "# Cwd File Content - Pytest Failing" in result.stdout
        assert "pytest" in result.stdout  # Should suggest pytest (from CWD file)
        assert "go test" not in result.stdout  # Should NOT suggest go (from repo file)

    def test_absolute_file_path_ignores_repo(self, tmp_path):
        """Test that absolute file paths ignore both CWD and repo."""
        # Create repo directory
        repo_dir = tmp_path / "project"
        repo_dir.mkdir()
        (repo_dir / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools"]')

        # Create issue file in completely different location
        other_dir = tmp_path / "other"
        other_dir.mkdir()
        issue_file = other_dir / "issue.txt"
        issue_file.write_text("npm test failing")

        # Run with absolute path - should use exact path
        result = run_plan_subprocess(
            ["--file", str(issue_file), "--repo", str(repo_dir), "--dry-run"],
            cwd=repo_dir,
        )

        assert result.returncode == 0, (
            f"Expected success, got {result.returncode}. stderr: {result.stderr}"
        )
        assert "# Npm Test Failing" in result.stdout

    def test_file_not_found_anywhere_returns_error(self, tmp_path):
        """Test that file not found in CWD or repo returns I/O error (exit 1)."""
        # Create repo directory (without issue file)
        repo_dir = tmp_path / "project"
        repo_dir.mkdir()
        (repo_dir / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools"]')

        # Create working directory (without issue file)
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        # Try to use non-existent file
        result = run_plan_subprocess(
            ["--file", "nonexistent.txt", "--repo", str(repo_dir)], cwd=work_dir
        )

        assert result.returncode == 1, (
            f"Expected I/O error (1), got {result.returncode}. stdout: {result.stdout}"
        )
        assert "Error reading file" in result.stderr
        assert "nonexistent.txt" in result.stderr

    def test_file_without_repo_uses_cwd_only(self, tmp_path):
        """Test that without --repo, file is resolved relative to CWD only."""
        # Create issue file in current directory
        issue_file = tmp_path / "issue.txt"
        issue_file.write_text("jest failing")

        # Run without --repo - should find file in CWD
        result = run_plan_subprocess(["--file", "issue.txt", "--dry-run"], cwd=tmp_path)

        assert result.returncode == 0, (
            f"Expected success, got {result.returncode}. stderr: {result.stderr}"
        )
        assert "# Jest Failing" in result.stdout

    def test_subdir_file_path_with_repo_fallback(self, tmp_path):
        """Test that subdirectory file paths work with repo fallback."""
        # Create repo directory with nested issue file
        repo_dir = tmp_path / "project"
        repo_dir.mkdir()
        (repo_dir / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools"]')

        issues_dir = repo_dir / "issues"
        issues_dir.mkdir()
        issue_file = issues_dir / "bug-report.txt"
        issue_file.write_text("docker build failing")

        # Create working directory (without the issues subdir)
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        # Run from work_dir with subdir path - should fallback to repo
        result = run_plan_subprocess(
            ["--file", "issues/bug-report.txt", "--repo", str(repo_dir), "--dry-run"],
            cwd=work_dir,
        )

        assert result.returncode == 0, (
            f"Expected success, got {result.returncode}. stderr: {result.stderr}"
        )
        assert "# Docker Build Failing" in result.stdout
