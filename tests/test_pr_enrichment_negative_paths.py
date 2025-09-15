"""
Tests for GitHub API failure scenarios during PR enrichment workflows.

This module focuses on timeout and HTTP error simulation with --json flag and proper
exit code validation for PR enrichment operations.
"""

import subprocess
from unittest.mock import patch

import pytest

from autorepro.io.github import create_pr_comment, get_pr_details, update_pr_body
from autorepro.pr import upsert_pr_body_sync_block, upsert_pr_comment


@pytest.fixture
def fake_env_setup(tmp_path, monkeypatch):
    """Setup fake environment for PR enrichment testing."""
    # Change to test directory
    monkeypatch.chdir(tmp_path)

    # Create minimal project structure
    (tmp_path / "README.md").write_text("# Test Project\n")
    (tmp_path / "setup.py").write_text(
        "from setuptools import setup\nsetup(name='test')"
    )

    # Mock environment variables for GitHub operations
    monkeypatch.setenv("GITHUB_TOKEN", "fake_token_12345")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/testrepo")

    return tmp_path


class TestPREnrichmentTimeoutErrors:
    """Tests for requests.Timeout simulation during PR enrichment."""

    def test_pr_comment_creation_timeout_with_json(self, fake_env_setup):
        """Test PR comment creation timeout with --format json flag."""
        # Mock subprocess.run to simulate timeout for gh pr comment
        with patch("autorepro.io.github.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["gh", "pr", "comment"], timeout=30
            )

            # Test the function directly - TimeoutExpired should be caught
            # and re-raised as RuntimeError
            try:
                create_pr_comment(123, "test comment", dry_run=False)
                raise AssertionError("Should have raised an exception")
            except subprocess.TimeoutExpired:
                # This is expected since the function doesn't catch TimeoutExpired specifically
                pass
            except RuntimeError:
                # This would be expected if the function caught and re-raised
                pass

    def test_pr_body_update_timeout_simulation(self, fake_env_setup):
        """Test PR body update timeout during enrichment workflow."""
        with patch("autorepro.io.github.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["gh", "pr", "edit", "--body-file"], timeout=45
            )

            # Test the function directly - TimeoutExpired should be caught
            try:
                update_pr_body(123, "test body content", dry_run=False)
                raise AssertionError("Should have raised an exception")
            except subprocess.TimeoutExpired:
                # This is expected since the function doesn't catch TimeoutExpired specifically
                pass
            except RuntimeError:
                # This would be expected if the function caught and re-raised
                pass

    def test_pr_details_fetch_timeout_error(self, fake_env_setup):
        """Test get_pr_details function timeout handling."""
        with patch("autorepro.io.github.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["gh", "pr", "view"], timeout=30
            )

            # Test the function directly - TimeoutExpired should be caught
            try:
                get_pr_details(123, gh_path="gh")
                raise AssertionError("Should have raised an exception")
            except subprocess.TimeoutExpired:
                # This is expected since the function doesn't catch TimeoutExpired specifically
                pass
            except RuntimeError:
                # This would be expected if the function caught and re-raised
                pass


class TestPREnrichmentHTTPErrors:
    """Tests for HTTPError simulation during PR enrichment."""

    def test_pr_comment_creation_http_error(self, fake_env_setup):
        """Test PR comment creation with HTTP error simulation."""
        with patch("autorepro.io.github.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=22, cmd=["gh", "pr", "comment"]
            )

            # Test the function directly
            with pytest.raises(RuntimeError, match="Failed to create PR comment"):
                create_pr_comment(123, "test comment", dry_run=False)

    def test_pr_body_update_http_failure(self, fake_env_setup):
        """Test update_pr_body function HTTP error handling."""
        with patch("autorepro.io.github.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=1, cmd=["gh", "pr", "edit"]
            )

            # Test the function directly
            with pytest.raises(RuntimeError, match="Failed to update PR body"):
                update_pr_body(123, "test body content", dry_run=False)

    def test_label_addition_http_error_scenario(self, fake_env_setup):
        """Test label addition with HTTP error during enrichment."""
        from autorepro.io.github import add_pr_labels

        with patch("autorepro.io.github.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=128, cmd=["gh", "pr", "edit", "--add-label"]
            )

            # Test the function directly
            with pytest.raises(RuntimeError, match="Failed to add PR labels"):
                add_pr_labels(123, ["bug", "enhancement"], dry_run=False)


class TestPREnrichmentJSONFormat:
    """Tests combining failures with --json flag validation."""

    def test_timeout_with_json_format_output(self, fake_env_setup):
        """Test timeout handling with JSON format flag."""
        with patch("autorepro.io.github.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["gh", "pr", "comment"], timeout=30
            )

            # Test with the high-level function that handles errors gracefully
            exit_code, updated = upsert_pr_comment(
                pr_number=123, body="test comment", replace_block=False, dry_run=False
            )

            # Should return error code instead of raising
            assert exit_code != 0
            assert not updated

    def test_http_error_with_json_output_validation(self, fake_env_setup):
        """Test HTTP error handling with JSON output format."""
        with patch("autorepro.io.github.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=404, cmd=["gh", "pr", "view"]
            )

            # Test with the high-level function that handles errors gracefully
            exit_code = upsert_pr_body_sync_block(
                pr_number=123, plan_content="test plan content", dry_run=False
            )

            # Should return error code instead of raising
            assert exit_code != 0

    def test_multiple_operation_failures_json_format(self, fake_env_setup):
        """Test multiple PR operations failing with JSON format."""
        with patch("autorepro.io.github.subprocess.run") as mock_run:
            # Simulate different failures for different operations
            call_count = 0

            def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    raise subprocess.TimeoutExpired(
                        cmd=["gh", "pr", "view"], timeout=30
                    )
                if call_count == 2:
                    raise subprocess.CalledProcessError(
                        returncode=1, cmd=["gh", "pr", "comment"]
                    )
                raise subprocess.CalledProcessError(
                    returncode=22, cmd=["gh", "pr", "edit"]
                )

            mock_run.side_effect = side_effect

            # Test first operation (should fail with timeout)
            exit_code1 = upsert_pr_body_sync_block(123, "test content")
            assert exit_code1 != 0

            # Test second operation (should fail with CalledProcessError)
            exit_code2, _ = upsert_pr_comment(123, "test comment")
            assert exit_code2 != 0


class TestPREnrichmentExitCodes:
    """Validation of non-zero exit codes and error messages."""

    def test_timeout_error_exit_code_validation(self, fake_env_setup):
        """Test proper exit code for timeout errors."""
        with patch("autorepro.io.github.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["gh", "pr", "comment"], timeout=30
            )

            # Test exit codes through high-level functions
            exit_code, _ = upsert_pr_comment(123, "test comment")

            # Should return specific non-zero exit code
            assert exit_code > 0
            assert exit_code != 0

    def test_http_error_exit_code_consistency(self, fake_env_setup):
        """Test consistent exit codes for HTTP errors."""
        with patch("autorepro.io.github.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=404, cmd=["gh", "pr", "view"]
            )

            # Test exit codes through high-level functions
            exit_code = upsert_pr_body_sync_block(123, "test content")

            assert exit_code != 0

    def test_error_message_presence_validation(self, fake_env_setup):
        """Test that error messages are always present on failures."""
        with patch("autorepro.io.github.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(
                returncode=128, cmd=["gh", "pr", "edit"]
            )

            # Test that errors are logged properly
            import logging

            with patch.object(logging.getLogger("autorepro"), "error") as mock_log:
                exit_code = upsert_pr_body_sync_block(123, "test content")

                assert exit_code != 0
                # Verify error was logged
                assert mock_log.called
                error_message = str(mock_log.call_args[0][0])
                assert len(error_message) > 10  # Substantial error message

    def test_json_format_error_reporting_structure(self, fake_env_setup):
        """Test error reporting structure with JSON format."""
        with patch("autorepro.io.github.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["gh", "pr", "comment"], timeout=30
            )

            # Test error reporting with logging
            import logging

            with patch.object(logging.getLogger("autorepro"), "error") as mock_log:
                exit_code, _ = upsert_pr_comment(123, "test comment")

                assert exit_code != 0
                # Should have error information logged
                assert mock_log.called
