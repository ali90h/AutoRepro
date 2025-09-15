"""Tests for --repo path stability and resolution functionality."""

import os

from tests.test_utils import run_autorepro_subprocess


def run_cli_subprocess(args, cwd=None):
    """Helper to run autorepro CLI via subprocess."""
    return run_autorepro_subprocess(args, cwd=cwd)


def create_project_markers(tmp_path, project_type="python"):
    """Create minimal marker files for different project types."""
    if project_type == "python":
        (tmp_path / "pyproject.toml").write_text(
            '[build-system]\nrequires = ["setuptools"]'
        )
    elif project_type == "node":
        (tmp_path / "package.json").write_text(
            '{"name": "test-project", "version": "1.0.0"}'
        )
    elif project_type == "go":
        (tmp_path / "go.mod").write_text("module test\n\ngo 1.19")


class TestRepoPathStability:
    """Test --repo path stability and resolution."""

    def test_plan_repo_path_resolved_consistently(self, tmp_path):
        """Test that --repo ./dir/ and --repo dir produce same result for plan."""
        # Create a test repo directory
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()
        create_project_markers(repo_dir, "python")

        # Test with ./dir/ format
        result1 = run_cli_subprocess(
            [
                "plan",
                "--desc",
                "pytest failing",
                "--out",
                "plan1.md",
                "--repo",
                f"./{repo_dir.name}/",
            ],
            cwd=tmp_path,
        )
        assert result1.returncode == 0

        # Test with dir format
        result2 = run_cli_subprocess(
            [
                "plan",
                "--desc",
                "pytest failing",
                "--out",
                "plan2.md",
                "--repo",
                repo_dir.name,
            ],
            cwd=tmp_path,
        )
        assert result2.returncode == 0

        # Both should create files in the repo directory
        plan1_file = repo_dir / "plan1.md"
        plan2_file = repo_dir / "plan2.md"
        assert plan1_file.exists(), "plan1.md should be created in repo directory"
        assert plan2_file.exists(), "plan2.md should be created in repo directory"

        # Content should be similar (both detecting Python)
        content1 = plan1_file.read_text()
        content2 = plan2_file.read_text()
        assert "pytest" in content1, "Should detect Python and suggest pytest"
        assert "pytest" in content2, "Should detect Python and suggest pytest"

    def test_init_repo_path_resolved_consistently(self, tmp_path):
        """Test that --repo ./dir/ and --repo dir produce same result for init."""
        # Create test repo directories
        repo_dir1 = tmp_path / "test_repo1"
        repo_dir1.mkdir()
        repo_dir2 = tmp_path / "test_repo2"
        repo_dir2.mkdir()

        # Test with ./dir/ format
        result1 = run_cli_subprocess(
            ["init", "--repo", f"./{repo_dir1.name}/"], cwd=tmp_path
        )
        assert result1.returncode == 0

        # Test with dir format
        result2 = run_cli_subprocess(["init", "--repo", repo_dir2.name], cwd=tmp_path)
        assert result2.returncode == 0

        # Both should create devcontainer files in their respective repo directories
        devcontainer1 = repo_dir1 / ".devcontainer" / "devcontainer.json"
        devcontainer2 = repo_dir2 / ".devcontainer" / "devcontainer.json"
        assert (
            devcontainer1.exists()
        ), "devcontainer.json should be created in repo_dir1"
        assert (
            devcontainer2.exists()
        ), "devcontainer.json should be created in repo_dir2"

    def test_repo_nonexistent_path_exit_2(self, tmp_path):
        """Test that nonexistent --repo path returns exit code 2."""
        result1 = run_cli_subprocess(
            ["plan", "--desc", "test", "--repo", "nonexistent_dir"], cwd=tmp_path
        )
        assert result1.returncode == 2
        assert "does not exist" in result1.stderr

        result2 = run_cli_subprocess(
            ["init", "--repo", "nonexistent_dir"], cwd=tmp_path
        )
        assert result2.returncode == 2
        assert "does not exist" in result2.stderr

    def test_repo_cwd_not_changed(self, tmp_path):
        """Test that --repo does not change the current working directory."""
        # Create repo directory
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()
        create_project_markers(repo_dir, "node")

        # Record original CWD
        original_cwd = os.getcwd()

        # Run plan command with --repo
        result1 = run_cli_subprocess(
            ["plan", "--desc", "npm test failing", "--repo", str(repo_dir)],
            cwd=tmp_path,
        )
        assert result1.returncode == 0

        # CWD should not have changed
        assert os.getcwd() == original_cwd, "CWD should not change after --repo usage"

        # File should be created in repo directory (not current directory)
        repo_plan_file = repo_dir / "repro.md"
        current_plan_file = tmp_path / "repro.md"
        assert repo_plan_file.exists(), "Plan should be created in repo directory"
        assert (
            not current_plan_file.exists()
        ), "Plan should NOT be created in current directory"

        # Run init command with --repo
        result2 = run_cli_subprocess(["init", "--repo", str(repo_dir)], cwd=tmp_path)
        assert result2.returncode == 0

        # CWD should still not have changed
        assert os.getcwd() == original_cwd, "CWD should not change after --repo usage"

        # Devcontainer should be created in repo directory
        repo_devcontainer = repo_dir / ".devcontainer" / "devcontainer.json"
        current_devcontainer = tmp_path / ".devcontainer" / "devcontainer.json"
        assert (
            repo_devcontainer.exists()
        ), "Devcontainer should be created in repo directory"
        assert (
            not current_devcontainer.exists()
        ), "Devcontainer should NOT be created in current directory"
