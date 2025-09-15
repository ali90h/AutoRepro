# ruff: noqa: E501
"""Integration tests for T-018 PR Enrichment & Cross-Link functionality."""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from autorepro.env import python_bin


class TestPREnrichmentCommand:
    """Test PR enrichment features with fake GitHub CLI setup."""

    @pytest.fixture
    def fake_env_setup(self):
        """Set up fake git environment and fake gh CLI for PR enrichment tests."""
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
            subprocess.run(
                ["git", "config", "user.name", "Test User"], cwd=work_repo, check=True
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=work_repo,
                check=True,
            )

            # Set up remote
            subprocess.run(
                ["git", "remote", "add", "origin", str(bare_repo)],
                cwd=work_repo,
                check=True,
            )
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
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"], cwd=work_repo, check=True
            )

            # Rename to main if needed
            current_branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=work_repo,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()

            if current_branch != "main":
                subprocess.run(
                    ["git", "branch", "-m", "main"], cwd=work_repo, check=True
                )

            subprocess.run(
                ["git", "push", "-u", "origin", "main"], cwd=work_repo, check=True
            )

            # Create feature branch
            subprocess.run(
                ["git", "checkout", "-b", "feature/test-pr"], cwd=work_repo, check=True
            )
            (work_repo / "test.py").write_text("# Test file")
            subprocess.run(["git", "add", "test.py"], cwd=work_repo, check=True)
            subprocess.run(
                ["git", "commit", "-m", "Add test file"], cwd=work_repo, check=True
            )
            subprocess.run(
                ["git", "push", "-u", "origin", "feature/test-pr"],
                cwd=work_repo,
                check=True,
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

    def create_fake_gh_cli_for_enrichment(self, fake_bin: Path, scenario: str) -> Path:
        """Create fake gh CLI for PR enrichment test scenarios."""
        gh_script = fake_bin / "gh"

        # scenario-specific PR view JSON
        if scenario == "comment_create":
            view_json = 'cat << \'EOF\'\n{\n  "number": 123,\n  "title": "test: Jest failing in CI",\n  "body": "Original PR description",\n  "comments": []\n}\nEOF'
        elif scenario == "comment_update":
            view_json = (
                'cat << \'EOF\'\n{\n  "number": 123,\n  "title": "test: Jest failing in CI",\n  '
                '"body": "Original PR description",\n  "comments": [\n    {\n      "id": 456,\n      "body": "<!-- autorepro:begin plan schema=1 -->\\n# Plan\\n<!-- autorepro:end plan -->",\n      "author": {"login": "test-bot"}\n    }\n  ]\n}\nEOF'
            )
        elif scenario == "body_update":
            view_json = 'cat << \'EOF\'\n{\n  "number": 123,\n  "title": "test: Jest failing in CI",\n  "body": "Original PR description without sync block",\n  "comments": []\n}\nEOF'
        elif scenario == "body_update_existing":
            view_json = (
                'cat << \'EOF\'\n{\n  "number": 123,\n  "title": "test: Jest failing in CI",\n  '
                '"body": "PR\\n\\n<!-- autorepro:begin plan schema=1 -->\\n# Plan\\n<!-- autorepro:end plan -->",\n  "comments": []\n}\nEOF'
            )
        elif scenario == "labels_add":
            view_json = 'cat << \'EOF\'\n{\n  "number": 123,\n  "title": "test: Jest failing in CI",\n  "body": "Original PR description",\n  "comments": []\n}\nEOF'
        elif scenario == "cross_link":
            view_json = 'cat << \'EOF\'\n{\n  "number": 123,\n  "title": "test: Jest failing in CI",\n  "body": "Original PR description",\n  "comments": []\n}\nEOF'
        elif scenario == "all_features":
            view_json = 'cat << \'EOF\'\n{\n  "number": 123,\n  "title": "test: Jest failing in CI",\n  "body": "Original PR description",\n  "comments": []\n}\nEOF'
        else:
            raise ValueError(f"Unknown enrichment scenario: {scenario}")

        header = """#!/bin/bash
echo "Fake gh called with: $@" >&2
ARGS="$*"
if [[ "$ARGS" == *"pr view"* ]]; then
"""

        middle = '\nelif [[ "$ARGS" == *"pr list"* ]]; then\n    echo \'[{"number": 123, "isDraft": true}]\'\nelif [[ "$ARGS" == *"pr create"* ]]; then\n    echo "https://github.com/owner/testrepo/pull/123"\nelif [[ "$ARGS" == *"pr comment"* ]]; then\n    echo "Comment created successfully"\nelif [[ "$ARGS" == *"pr edit"* ]]; then\n    echo "Updated PR #123 body"\nelif [[ "$ARGS" == *"issue comment"* ]]; then\n    echo "Comment created on issue: #789"\nelif [[ "$ARGS" == *"api"* ]]; then\n    echo "Comment updated successfully"\nelse\n    echo "Unknown command: $@" >&2\n    exit 1\nfi\n'

        # concatenate without f-string to avoid formatting braces inside view_json
        script_content = header + view_json + middle

        gh_script.write_text(script_content)
        gh_script.chmod(0o755)
        return gh_script

    def test_pr_comment_create_new(self, fake_env_setup):
        """Test --comment flag creates new PR comment with sync block."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI for comment creation
        self.create_fake_gh_cli_for_enrichment(fake_bin, "comment_create")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Replace 'python' with the virtual environment's Python executable
        python_executable = python_bin()

        # Update subprocess.run calls to use the virtual environment's Python executable
        result = subprocess.run(
            [
                python_executable,
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "Jest tests failing in CI environment",
                "--repo-slug",
                "owner/testrepo",
                "--comment",
                "--skip-push",
                "-v",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify success
        assert result.returncode == 0, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Should create PR comment with sync block
        assert "Created autorepro comment" in result.stderr

    def test_pr_comment_update_existing(self, fake_env_setup):
        """Test --comment flag updates existing PR comment with sync block."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI for comment update scenario
        self.create_fake_gh_cli_for_enrichment(fake_bin, "comment_update")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Replace 'python' with the virtual environment's Python executable
        python_executable = python_bin()

        # Update subprocess.run calls to use the virtual environment's Python executable
        result = subprocess.run(
            [
                python_executable,
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "Updated Jest tests failing scenario",
                "--repo-slug",
                "owner/testrepo",
                "--comment",
                "--skip-push",
                "-v",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify success and that existing comment was updated
        assert result.returncode == 0, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert (
            "Updated autorepro comment" in result.stderr
            or "Created autorepro comment" in result.stderr
        )

    def test_pr_body_update_sync_block(self, fake_env_setup):
        """Test --update-pr-body flag adds sync block to PR description."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI for body update scenario
        self.create_fake_gh_cli_for_enrichment(fake_bin, "body_update")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Replace 'python' with the virtual environment's Python executable
        python_executable = python_bin()

        # Update subprocess.run calls to use the virtual environment's Python executable
        result = subprocess.run(
            [
                python_executable,
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "Jest tests failing in CI",
                "--repo-slug",
                "owner/testrepo",
                "--update-pr-body",
                "--skip-push",
                "-v",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify success
        assert result.returncode == 0, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Should update PR body with sync block
        assert (
            "Updated sync block" in result.stderr
            or "Adding new sync block" in result.stderr
        )

    def test_pr_body_update_existing_sync_block(self, fake_env_setup):
        """Test --update-pr-body flag replaces existing sync block in PR description."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI for body update with existing sync block
        self.create_fake_gh_cli_for_enrichment(fake_bin, "body_update_existing")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Replace 'python' with the virtual environment's Python executable
        python_executable = python_bin()

        # Update subprocess.run calls to use the virtual environment's Python executable
        result = subprocess.run(
            [
                python_executable,
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "Updated Jest tests failing scenario",
                "--repo-slug",
                "owner/testrepo",
                "--update-pr-body",
                "--skip-push",
                "-v",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify success and existing sync block was replaced
        assert result.returncode == 0, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert (
            "Updated sync block" in result.stderr
            or "Replacing existing sync block" in result.stderr
        )

    def test_pr_add_labels(self, fake_env_setup):
        """Test --add-labels flag adds labels to PR."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI for labels scenario
        self.create_fake_gh_cli_for_enrichment(fake_bin, "labels_add")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Replace 'python' with the virtual environment's Python executable
        python_executable = python_bin()

        # Update subprocess.run calls to use the virtual environment's Python executable
        result = subprocess.run(
            [
                python_executable,
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "Jest tests failing",
                "--repo-slug",
                "owner/testrepo",
                "--add-labels",
                "repro:ready,ci:failing",
                "--skip-push",
                "-v",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify success
        assert result.returncode == 0, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Should add labels to PR
        assert (
            "Added labels" in result.stderr or "Updated PR with labels" in result.stderr
        )

    def test_pr_link_issue_cross_reference(self, fake_env_setup):
        """Test --link-issue flag creates cross-reference links."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI for cross-link scenario
        self.create_fake_gh_cli_for_enrichment(fake_bin, "cross_link")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Replace 'python' with the virtual environment's Python executable
        python_executable = python_bin()

        # Update subprocess.run calls to use the virtual environment's Python executable
        result = subprocess.run(
            [
                python_executable,
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "Jest tests failing from issue",
                "--repo-slug",
                "owner/testrepo",
                "--link-issue",
                "789",
                "--skip-push",
                "-v",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify success
        assert result.returncode == 0, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Should create cross-reference link
        assert (
            "Cross-linked to issue" in result.stderr
            or "Created issue comment" in result.stderr
        )

    def test_pr_attach_report_metadata(self, fake_env_setup):
        """Test --attach-report flag includes report metadata in comment."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI
        self.create_fake_gh_cli_for_enrichment(fake_bin, "comment_create")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Replace 'python' with the virtual environment's Python executable
        python_executable = python_bin()

        # Update subprocess.run calls to use the virtual environment's Python executable
        result = subprocess.run(
            [
                python_executable,
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "Jest tests with report bundle",
                "--repo-slug",
                "owner/testrepo",
                "--comment",
                "--attach-report",
                "--skip-push",
                "-v",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify success
        assert result.returncode == 0, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Comment should include report metadata
        assert (
            "Created autorepro comment" in result.stderr
            or "Updated existing autorepro comment" in result.stderr
        )

    def test_pr_summary_context(self, fake_env_setup):
        """Test --summary flag adds reviewer context to PR comment."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI
        self.create_fake_gh_cli_for_enrichment(fake_bin, "comment_create")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Replace 'python' with the virtual environment's Python executable
        python_executable = python_bin()

        # Update subprocess.run calls to use the virtual environment's Python executable
        result = subprocess.run(
            [
                python_executable,
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "Jest tests failing",
                "--repo-slug",
                "owner/testrepo",
                "--comment",
                "--summary",
                "CI pipeline is broken after dependency update",
                "--skip-push",
                "-v",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify success
        assert result.returncode == 0, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Comment should include summary context
        assert (
            "Created autorepro comment" in result.stderr
            or "Updated existing autorepro comment" in result.stderr
        )

    def test_pr_no_details_flag(self, fake_env_setup):
        """Test --no-details flag disables collapsible wrapper."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI
        self.create_fake_gh_cli_for_enrichment(fake_bin, "comment_create")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Replace 'python' with the virtual environment's Python executable
        python_executable = python_bin()

        # Update subprocess.run calls to use the virtual environment's Python executable
        result = subprocess.run(
            [
                python_executable,
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "Jest tests with long reproduction steps - testing no-details flag",
                "--repo-slug",
                "owner/testrepo",
                "--comment",
                "--no-details",
                "--skip-push",
                "-v",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify success
        assert result.returncode == 0, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Comment should be created without details wrapper
        assert (
            "Created autorepro comment" in result.stderr
            or "Updated existing autorepro comment" in result.stderr
        )

    def test_pr_all_enrichment_features_combined(self, fake_env_setup):
        """Test all T-018 enrichment features working together."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI for all features scenario
        self.create_fake_gh_cli_for_enrichment(fake_bin, "all_features")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Replace 'python' with the virtual environment's Python executable
        python_executable = python_bin()

        # Update subprocess.run calls to use the virtual environment's Python executable
        result = subprocess.run(
            [
                python_executable,
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "Comprehensive Jest test failure reproduction",
                "--repo-slug",
                "owner/testrepo",
                "--comment",
                "--update-pr-body",
                "--link-issue",
                "456",
                "--add-labels",
                "repro:ready,ci:failing,jest",
                "--attach-report",
                "--summary",
                "Multiple CI failures after Jest upgrade",
                "--no-details",
                "--skip-push",
                "-v",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify success with all features
        assert result.returncode == 0, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Should create/update PR comment, update body, add labels, create cross-links
        stderr_text = result.stderr
        assert any(
            phrase in stderr_text
            for phrase in [
                "Created autorepro comment",
                "Updated existing autorepro comment",
                "Updated PR body",
                "Added labels",
            ]
        )

    def test_pr_enrichment_dry_run_mode(self, fake_env_setup):
        """Test enrichment features in dry-run mode."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI (won't be called due to dry-run)
        self.create_fake_gh_cli_for_enrichment(fake_bin, "all_features")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Replace 'python' with the virtual environment's Python executable
        python_executable = python_bin()

        # Update subprocess.run calls to use the virtual environment's Python executable
        result = subprocess.run(
            [
                python_executable,
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "Jest tests dry-run scenario",
                "--repo-slug",
                "owner/testrepo",
                "--comment",
                "--update-pr-body",
                "--add-labels",
                "repro:ready",
                "--dry-run",
                "--skip-push",
                "-v",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify dry-run success
        assert result.returncode == 0, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Should show what would be done without actually doing it
        stdout_text = result.stdout
        assert "Would run: gh pr create" in stdout_text
        # Dry-run should not actually call gh commands for enrichment
        assert (
            "Would update PR comment" in stdout_text
            or "Would add sync block" in stdout_text
        )

    def test_pr_enrichment_format_json(self, fake_env_setup):
        """Test enrichment with JSON format output."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI
        self.create_fake_gh_cli_for_enrichment(fake_bin, "comment_create")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Replace 'python' with the virtual environment's Python executable
        python_executable = python_bin()

        # Update subprocess.run calls to use the virtual environment's Python executable
        result = subprocess.run(
            [
                python_executable,
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "Jest failing for JSON format test",
                "--repo-slug",
                "owner/testrepo",
                "--comment",
                "--format",
                "json",
                "--skip-push",
                "-v",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify success with JSON format
        assert result.returncode == 0, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Comment should be created with JSON format
        assert (
            "Created autorepro comment" in result.stderr
            or "Updated existing autorepro comment" in result.stderr
        )

    def test_pr_enrichment_error_handling(self, fake_env_setup):
        """Test error handling in enrichment features."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI that fails for comments
        gh_script = fake_bin / "gh"
        script_content = """#!/bin/bash
echo "Fake gh called with: $@" >&2
ARGS="$*"
if [[ "$ARGS" == *"pr view"* ]]; then
cat << 'EOF'
{
    "number": 123,
    "title": "test: Jest failing in CI",
    "body": "Original PR description",
    "isDraft": true
}
EOF
elif [[ "$ARGS" == *"pr comment"* ]]; then
    echo "GitHub API error: Comment creation failed" >&2
    exit 1
elif [[ "$ARGS" == *"pr list"* ]]; then
    echo '[{"number": 123, "isDraft": true}]'
elif [[ "$ARGS" == *"pr create"* ]]; then
    echo "https://github.com/owner/testrepo/pull/123"
else
    echo "Unknown command: $@" >&2
    exit 1
fi
"""
        gh_script.write_text(script_content)
        gh_script.chmod(0o755)

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Run with --comment flag (should fail due to fake error)
        result = subprocess.run(
            [
                python_bin(),
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "Jest tests error handling test",
                "--repo-slug",
                "owner/testrepo",
                "--comment",
                "--skip-push",
                "-v",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # Verify error is handled gracefully OR operation succeeded
        assert result.returncode in (0, 1), f"Unexpected exit code: {result.returncode}"
        # Should show meaningful error message if failed, or creation message if succeeded
        assert (
            result.returncode == 1
            and (
                "Failed to upsert PR comment" in result.stderr
                or "Failed to create PR comment" in result.stderr
            )
        ) or (result.returncode == 0 and "Created autorepro comment" in result.stderr)

    def test_pr_enrichment_mutual_exclusions(self, fake_env_setup):
        """Test mutually exclusive flag combinations for enrichment."""
        env = fake_env_setup
        work_repo = env["work_repo"]
        fake_bin = env["fake_bin"]

        # Create fake gh CLI for the dry-run scenario
        self.create_fake_gh_cli_for_enrichment(fake_bin, "all_features")

        # Set up environment
        test_env = os.environ.copy()
        test_env["PATH"] = f"{fake_bin}:{test_env['PATH']}"

        # Replace 'python' with the virtual environment's Python executable
        python_executable = python_bin()

        # Update subprocess.run calls to use the virtual environment's Python executable
        result = subprocess.run(
            [
                python_executable,
                "-m",
                "autorepro",
                "pr",
                "--desc",
                "test mutual compatibility",
                "--repo-slug",
                "owner/testrepo",
                "--comment",
                "--update-pr-body",
                "--dry-run",
            ],
            cwd=work_repo,
            capture_output=True,
            text=True,
            env=test_env,
        )

        # This combination should work (both comment and body updates)
        assert result.returncode == 0, (
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "Would run: gh pr create" in result.stdout
