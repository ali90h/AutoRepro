"""Integration tests for autorepro pr command with fully local/offline setup."""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest


class TestPRCommand:
    """Test PR command with fake git repos and fake gh CLI."""

    @pytest.fixture
    def fake_env_setup(self):
        """Set up fake git environment and fake gh CLI."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create fake bare repository
            bare_repo = temp_path / "fake-origin.git"
            subprocess.run(["git", "init", "--bare", str(bare_repo)], check=True)

            # Create working repository
            work_repo = temp_path / "work-repo"
            work_repo.mkdir()

            # Initialize working repo
            subprocess.run(["git", "init"], cwd=work_repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=work_repo, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"], cwd=work_repo, check=True
            )

            # Set up remote that works for both pushing and ls-remote
            # Use bare repo for both fetch and push during testing
            subprocess.run(
                ["git", "remote", "add", "origin", str(bare_repo)], cwd=work_repo, check=True
            )

            # Also set up fake GitHub URL for slug detection - we'll override this per test
            subprocess.run(
                [
                    "git",
                    "config",
                    "remote.origin.autorepro-test-url",
                    "https://github.com/owner/testrepo.git",
                ],
                cwd=work_repo,
                check=True,
            )

            # Create initial commit and branch
            (work_repo / "README.md").write_text("# Test Repo")
            subprocess.run(["git", "add", "README.md"], cwd=work_repo, check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=work_repo, check=True)

            # Rename default branch to main if needed
            current_branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=work_repo,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            if current_branch != "main":
                subprocess.run(["git", "branch", "-m", "main"], cwd=work_repo, check=True)

            subprocess.run(["git", "push", "-u", "origin", "main"], cwd=work_repo, check=True)

            # Create feature branch
            subprocess.run(["git", "checkout", "-b", "feature/test-pr"], cwd=work_repo, check=True)
            (work_repo / "test.py").write_text("# Test file")
            subprocess.run(["git", "add", "test.py"], cwd=work_repo, check=True)
            subprocess.run(["git", "commit", "-m", "Add test file"], cwd=work_repo, check=True)
            subprocess.run(
                ["git", "push", "-u", "origin", "feature/test-pr"], cwd=work_repo, check=True
            )

            # Create fake gh CLI tool directory
            fake_bin = temp_path / "fakebin"
            fake_bin.mkdir()

            yield {
                "work_repo": work_repo,
                "bare_repo": bare_repo,
                "fake_bin": fake_bin,
                "temp_path": temp_path,
            }

    def create_fake_gh_cli(self, fake_bin: Path, scenario: str) -> Path:
        """Create fake gh CLI tool for different test scenarios."""
        gh_script = fake_bin / "gh"

        if scenario == "create_new":
            # Scenario: no existing PRs, create new one
            script_content = """#!/bin/bash
echo "Fake gh called with: $@" >&2
case "$1 $2" in
  "pr list") echo '[]' ;;
  "pr create") echo "https://github.com/owner/testrepo/pull/123" ;;
  *) echo "Unknown command: $@" >&2; exit 1 ;;
esac
"""
        elif scenario == "update_existing":
            # Scenario: existing draft PR, update it
            script_content = """#!/bin/bash
echo "Fake gh called with: $@" >&2
case "$1 $2" in
  "pr list") echo '[{"number": 42, "isDraft": true}]' ;;
  "pr edit") echo "Updated PR #42" ;;
  *) echo "Unknown command: $@" >&2; exit 1 ;;
esac
"""
        elif scenario == "gh_failure":
            # Scenario: gh CLI fails
            script_content = """#!/bin/bash
echo "Fake gh called with: $@" >&2
echo "Error: GitHub CLI authentication failed" >&2
exit 1
"""
        else:
            raise ValueError(f"Unknown scenario: {scenario}")

        gh_script.write_text(script_content)
        gh_script.chmod(0o755)
        return gh_script

    def test_pr_create_new(self, fake_env_setup):
        """Test creating a new PR when no existing draft PRs exist."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI for create scenario
        self.create_fake_gh_cli(fake_bin, "create_new")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Run autorepro pr command
        result = subprocess.run(
            [
                "python",
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "pytest failing in CI environment",
                "--repo-slug",
                "owner/testrepo",
                "--dry-run",  # Don't actually call gh
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify exit code and output
        assert result.returncode == 0
        assert "Would run: gh pr create" in result.stdout
        assert "chore(repro): Pytest Failing In Ci Environment [draft]" in result.stdout
        assert "--base main" in result.stdout
        assert "--head feature/test-pr" in result.stdout
        assert "--draft" in result.stdout

    def test_pr_create_new_live(self, fake_env_setup):
        """Test actually running gh pr create (with fake gh)."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI for create scenario
        self.create_fake_gh_cli(fake_bin, "create_new")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Run autorepro pr command (live)
        result = subprocess.run(
            [
                "python",
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "pytest test failure",
                "--repo-slug",
                "owner/testrepo",
                "-v",  # Add verbose output to see what's happening
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify exit code and output
        assert result.returncode == 0, f"stdout: {result.stdout}\nstderr: {result.stderr}"
        # Check that fake gh was called (look for the PR URL it returns)
        assert "Created PR: https://github.com/owner/testrepo/pull/123" in result.stderr
        assert "Created draft PR from branch feature/test-pr" in result.stderr

    def test_pr_update_existing(self, fake_env_setup):
        """Test updating an existing draft PR."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI for update scenario
        self.create_fake_gh_cli(fake_bin, "update_existing")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Run autorepro pr command with update flag
        result = subprocess.run(
            [
                "python",
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "updated pytest failing scenario",
                "--repo-slug",
                "owner/testrepo",
                "--update-if-exists",
                "-v",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify exit code and output
        assert result.returncode == 0, f"stderr: {result.stderr}"
        # Check that existing PR was updated (look for update message)
        assert "Updated PR #42" in result.stderr or "Updated draft PR #42" in result.stderr

    def test_pr_gh_failure(self, fake_env_setup):
        """Test handling of GitHub CLI failure."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI that fails
        self.create_fake_gh_cli(fake_bin, "gh_failure")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Run autorepro pr command
        result = subprocess.run(
            [
                "python",
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "test failure scenario",
                "--repo-slug",
                "owner/testrepo",
                "-v",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify exit code is 1 (failure)
        assert result.returncode == 1
        # Verify error message about GitHub CLI failure
        assert "GitHub CLI error" in result.stderr or "Error creating PR" in result.stderr

    def test_pr_skip_push_flag(self, fake_env_setup):
        """Test --skip-push flag behavior."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI
        self.create_fake_gh_cli(fake_bin, "create_new")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Run with --skip-push and --dry-run to check behavior
        result = subprocess.run(
            [
                "python",
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "test skip push",
                "--repo-slug",
                "owner/testrepo",
                "--skip-push",
                "--dry-run",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify it succeeds and doesn't mention pushing
        assert result.returncode == 0
        assert "Would run: gh pr create" in result.stdout
        # No push-related messages should appear
        assert "Pushed branch" not in result.stderr
        assert "Push to origin failed" not in result.stderr

    def test_pr_missing_branch_with_skip_push(self, fake_env_setup):
        """Test --skip-push with branch that doesn't exist on remote."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create a new branch that doesn't exist on remote
        subprocess.run(["git", "checkout", "-b", "feature/new-branch"], cwd=work_repo, check=True)

        # Create fake gh CLI
        self.create_fake_gh_cli(fake_bin, "create_new")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Run with --skip-push (should fail because branch not on remote)
        result = subprocess.run(
            [
                "python",
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "test missing branch",
                "--repo-slug",
                "owner/testrepo",
                "--skip-push",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify it fails with helpful message
        assert result.returncode == 1
        assert "does not exist on origin" in result.stderr
        assert "Push required:" in result.stderr
        assert "Or remove --skip-push" in result.stderr

    def test_pr_custom_title_and_body(self, fake_env_setup):
        """Test PR with custom title and body."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]
        temp_path = env["temp_path"]

        # Create custom body file
        body_file = temp_path / "custom-body.md"
        body_file.write_text("# Custom PR Body\n\nThis is a custom body for testing.\n")

        # Create fake gh CLI
        self.create_fake_gh_cli(fake_bin, "create_new")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Run with custom title and body
        result = subprocess.run(
            [
                "python",
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "test issue",
                "--title",
                "fix: custom PR title",
                "--body",
                str(body_file),
                "--repo-slug",
                "owner/testrepo",
                "--skip-push",
                "--dry-run",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify custom title is used
        assert result.returncode == 0
        assert "--title fix: custom PR title" in result.stdout
        # Body file should be referenced (temp file created)
        assert "--body-file" in result.stdout

    def test_pr_ready_flag(self, fake_env_setup):
        """Test creating ready (non-draft) PR."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI
        self.create_fake_gh_cli(fake_bin, "create_new")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Run with --ready flag
        result = subprocess.run(
            [
                "python",
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "ready pr test",
                "--ready",
                "--repo-slug",
                "owner/testrepo",
                "--skip-push",
                "--dry-run",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify it's not a draft
        assert result.returncode == 0
        assert "Ready Pr Test" in result.stdout  # No [draft] in title
        assert "--draft" not in result.stdout  # No --draft flag

    def test_pr_labels_and_assignees(self, fake_env_setup):
        """Test PR with labels and assignees."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI
        self.create_fake_gh_cli(fake_bin, "create_new")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Run with labels and assignees
        result = subprocess.run(
            [
                "python",
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "test with metadata",
                "--label",
                "bug",
                "--label",
                "testing",
                "--assignee",
                "testuser",
                "--reviewer",
                "maintainer",
                "--repo-slug",
                "owner/testrepo",
                "--skip-push",
                "--dry-run",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify labels and assignees are included
        assert result.returncode == 0
        assert "--label bug,testing" in result.stdout
        assert "--assignee testuser" in result.stdout
        assert "--reviewer maintainer" in result.stdout

    def test_pr_strict_mode_failure(self, fake_env_setup):
        """Test PR command with strict mode when no commands meet min-score."""
        env = fake_env_setup
        work_repo = env["work_repo"]

        # Run with strict mode and high min-score
        result = subprocess.run(
            [
                "python",
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "some random issue without specific keywords",
                "--strict",
                "--min-score",
                "5",
                "--repo-slug",
                "owner/testrepo",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
        )

        # Verify it fails with strict mode error
        assert result.returncode == 1
        assert "no candidate commands above min-score=5" in result.stderr
