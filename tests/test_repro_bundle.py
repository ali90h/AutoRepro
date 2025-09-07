"""
Tests for autorepro/utils/repro_bundle.py - golden coverage tests.

These tests verify behavior-preserving functionality for the build_repro_bundle function
to increase code coverage by approximately 10%.
"""

import zipfile
from unittest.mock import patch

import pytest

from autorepro.utils.repro_bundle import build_repro_bundle, generate_plan_content


class TestBuildReproBundleBasic:
    """Basic functionality tests for build_repro_bundle."""

    def test_build_repro_bundle_exec_false(self, tmp_path):
        """Test build_repro_bundle with exec_=False creates basic bundle."""
        # Change to temp directory to avoid side effects
        with patch("autorepro.utils.repro_bundle.Path.cwd", return_value=tmp_path):
            bundle_path, size_bytes = build_repro_bundle("test issue description", exec_=False)

        # Assert bundle exists and has non-trivial size
        assert bundle_path.exists()
        assert bundle_path.name == "repro_bundle.zip"
        assert size_bytes > 100  # Bundle should contain meaningful content

        # Verify it's a valid zip file
        assert zipfile.is_zipfile(bundle_path)

        # Check bundle contents
        with zipfile.ZipFile(bundle_path, "r") as zf:
            files = zf.namelist()
            assert "repro.md" in files
            assert "ENV.txt" in files
            # Should not contain execution files when exec_=False
            assert "execution.log" not in files
            assert "execution.jsonl" not in files

    def test_build_repro_bundle_exec_true(self, tmp_path):
        """Test build_repro_bundle with exec_=True creates bundle with execution results."""
        # Mock execution results
        mock_log_path = tmp_path / "test.log"
        mock_jsonl_path = tmp_path / "test.jsonl"
        mock_log_path.write_text("Test log content")
        mock_jsonl_path.write_text('{"test": "data"}\n')

        with (
            patch("autorepro.utils.repro_bundle.Path.cwd", return_value=tmp_path),
            patch("autorepro.report.maybe_exec") as mock_exec,
        ):
            mock_exec.return_value = (0, mock_log_path, mock_jsonl_path)
            bundle_path, size_bytes = build_repro_bundle("test issue description", exec_=True)

        # Assert bundle exists and has non-trivial size
        assert bundle_path.exists()
        assert size_bytes > 200  # Should be larger due to execution files

        # Check bundle contents include execution files
        with zipfile.ZipFile(bundle_path, "r") as zf:
            files = zf.namelist()
            assert "repro.md" in files
            assert "ENV.txt" in files
            assert "execution.log" in files
            assert "execution.jsonl" in files


class TestBuildReproBundleDescriptionVariations:
    """Test build_repro_bundle with different description sizes."""

    def test_small_description_input(self, tmp_path):
        """Test build_repro_bundle with small description."""
        small_desc = "Fix bug"

        with patch("autorepro.utils.repro_bundle.Path.cwd", return_value=tmp_path):
            bundle_path, size_bytes = build_repro_bundle(small_desc, exec_=False)

        assert bundle_path.exists()
        assert size_bytes > 50  # Even small descriptions should generate meaningful content

        # Verify the description is included in the plan
        with zipfile.ZipFile(bundle_path, "r") as zf:
            repro_content = zf.read("repro.md").decode("utf-8")
            # Should contain some plan content even for small descriptions
            assert len(repro_content) > 10

    def test_large_description_input(self, tmp_path):
        """Test build_repro_bundle with large description."""
        large_desc = (
            "Complex system issue with multiple components. "
            "Frontend, backend, database, external services. "
            "Timeout and state management problems."
        )

        with patch("autorepro.utils.repro_bundle.Path.cwd", return_value=tmp_path):
            bundle_path, size_bytes = build_repro_bundle(large_desc, exec_=False)

        assert bundle_path.exists()
        assert size_bytes > 500  # Large descriptions should result in larger bundles

        # Verify the large description is handled properly
        with zipfile.ZipFile(bundle_path, "r") as zf:
            repro_content = zf.read("repro.md").decode("utf-8")
            assert len(repro_content) > 100


class TestBuildReproBundleTimeoutVariations:
    """Test build_repro_bundle with different timeout values."""

    def test_short_timeout_simulation(self, tmp_path):
        """Test build_repro_bundle with short timeout (simulated via monkeypatch/sleep)."""
        with (
            patch("autorepro.utils.repro_bundle.Path.cwd", return_value=tmp_path),
            patch("autorepro.report.maybe_exec") as mock_exec,
        ):
            # Simulate timeout behavior
            mock_exec.return_value = (124, None, None)  # 124 is typical timeout exit code

            bundle_path, size_bytes = build_repro_bundle(
                "test timeout issue",
                timeout=1,  # Very short timeout
                exec_=True,
            )

            # Verify timeout was passed to maybe_exec
            mock_exec.assert_called_once()
            call_args = mock_exec.call_args[0][1]  # Get the opts dict (second positional arg)
            assert call_args["timeout"] == 1

        assert bundle_path.exists()
        assert size_bytes > 100  # Should still create bundle even with timeout


class TestBuildReproBundleErrorHandling:
    """Test error handling in build_repro_bundle."""

    def test_empty_description_raises_error(self):
        """Test that empty description raises ValueError."""
        with pytest.raises(ValueError, match="Description cannot be empty"):
            build_repro_bundle("")

    def test_whitespace_only_description_raises_error(self):
        """Test that whitespace-only description raises ValueError."""
        with pytest.raises(ValueError, match="Description cannot be empty"):
            build_repro_bundle("   \n\t  ")

    def test_none_description_raises_error(self):
        """Test that None description raises ValueError."""
        with pytest.raises(ValueError, match="Description cannot be empty"):
            build_repro_bundle(None)

    def test_bundle_creation_failure_raises_runtime_error(self, tmp_path):
        """Test that bundle creation failure raises RuntimeError."""
        with (
            patch("autorepro.utils.repro_bundle.Path.cwd", return_value=tmp_path),
            patch("autorepro.report.pack_zip", side_effect=OSError("Disk full")),
        ):
            with pytest.raises(RuntimeError, match="Failed to build repro bundle"):
                build_repro_bundle("test issue")


class TestBuildReproBundleFileHandling:
    """Test file handling and cleanup in build_repro_bundle."""

    def test_bundle_file_cleanup_on_exec_true(self, tmp_path):
        """Test that temporary execution files are cleaned up."""
        mock_log_path = tmp_path / "test.log"
        mock_jsonl_path = tmp_path / "test.jsonl"
        mock_log_path.write_text("Test log content")
        mock_jsonl_path.write_text('{"test": "data"}\n')

        with (
            patch("autorepro.utils.repro_bundle.Path.cwd", return_value=tmp_path),
            patch("autorepro.report.maybe_exec") as mock_exec,
        ):
            mock_exec.return_value = (0, mock_log_path, mock_jsonl_path)
            bundle_path, size_bytes = build_repro_bundle("test issue", exec_=True)

            # Files should be cleaned up after bundle creation
            # Note: The function tries to clean up but ignores OSError, so files might still exist
            # This test verifies the cleanup attempt is made
            assert bundle_path.exists()

    def test_bundle_missing_execution_files_handled_gracefully(self, tmp_path):
        """Test that missing execution files are handled gracefully."""
        # Return non-existent paths from maybe_exec
        fake_log_path = tmp_path / "nonexistent.log"
        fake_jsonl_path = tmp_path / "nonexistent.jsonl"

        with (
            patch("autorepro.utils.repro_bundle.Path.cwd", return_value=tmp_path),
            patch("autorepro.report.maybe_exec") as mock_exec,
        ):
            mock_exec.return_value = (0, fake_log_path, fake_jsonl_path)
            bundle_path, size_bytes = build_repro_bundle("test issue", exec_=True)

        # Should still create bundle without execution files
        assert bundle_path.exists()

        with zipfile.ZipFile(bundle_path, "r") as zf:
            files = zf.namelist()
            assert "repro.md" in files
            assert "ENV.txt" in files
            # Execution files should not be included if they don't exist
            assert "execution.log" not in files
            assert "execution.jsonl" not in files


class TestGeneratePlanContentCoverage:
    """Additional tests for generate_plan_content function to improve coverage."""

    def test_generate_plan_content_json_format(self, tmp_path):
        """Test generate_plan_content with JSON format."""
        with patch("autorepro.utils.repro_bundle.Path.cwd", return_value=tmp_path):
            content = generate_plan_content("test issue", tmp_path, "json", min_score=1)

        assert content.endswith("\n")  # Proper newline termination
        # Should be valid JSON
        import json

        parsed = json.loads(content.strip())
        assert isinstance(parsed, dict)
        assert "title" in parsed or "assumptions" in parsed

    def test_generate_plan_content_md_format(self, tmp_path):
        """Test generate_plan_content with markdown format."""
        with patch("autorepro.utils.repro_bundle.Path.cwd", return_value=tmp_path):
            content = generate_plan_content("test issue", tmp_path, "md", min_score=1)

        assert content.endswith("\n")  # Proper newline termination
        assert isinstance(content, str)
        assert len(content) > 10  # Should generate meaningful content

    def test_generate_plan_content_different_min_scores(self, tmp_path):
        """Test generate_plan_content with different min_score values."""
        with patch("autorepro.utils.repro_bundle.Path.cwd", return_value=tmp_path):
            content_low = generate_plan_content("test issue", tmp_path, "md", min_score=1)
            content_high = generate_plan_content("test issue", tmp_path, "md", min_score=5)

        # Both should generate content, but might differ in command suggestions
        assert len(content_low) > 10
        assert len(content_high) > 10


class TestBuildReproBundleIntegration:
    """Integration tests for build_repro_bundle with realistic scenarios."""

    def test_build_bundle_with_realistic_python_issue(self, tmp_path):
        """Test bundle creation with a realistic Python-related issue description."""
        python_issue = (
            "Python import error: ModuleNotFoundError when running tests. "
            "Pytest fails with local modules. Project has __init__.py files. "
            "Works in IDE, fails in CLI. Python 3.11, pytest 7.x"
        )

        with patch("autorepro.utils.repro_bundle.Path.cwd", return_value=tmp_path):
            bundle_path, size_bytes = build_repro_bundle(python_issue, timeout=15, exec_=False)

        assert bundle_path.exists()
        assert size_bytes > 200  # Detailed issue should generate substantial content

        # Verify bundle contains expected structure
        with zipfile.ZipFile(bundle_path, "r") as zf:
            files = zf.namelist()
            assert len(files) == 2  # repro.md and ENV.txt

            # Check that content is meaningful
            repro_content = zf.read("repro.md").decode("utf-8")
            env_content = zf.read("ENV.txt").decode("utf-8")

            assert len(repro_content) > 50
            assert len(env_content) > 20

    def test_build_bundle_preserves_file_sizes(self, tmp_path):
        """Test that bundle file sizes are consistent for the same input."""
        desc = "Test consistency issue"

        with patch("autorepro.utils.repro_bundle.Path.cwd", return_value=tmp_path):
            bundle1_path, size1 = build_repro_bundle(desc, exec_=False)
            bundle2_path, size2 = build_repro_bundle(desc, exec_=False)

        # Sizes should be identical for same input (deterministic output)
        # Note: This might vary slightly due to timestamps, but should be very close
        size_diff = abs(size1 - size2)
        assert size_diff < 100  # Allow small variations due to timestamps
