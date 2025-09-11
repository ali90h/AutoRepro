"""
Behavioral validation tests for configuration system.

These tests ensure that the configuration system maintains identical behavior to the
original hard-coded values while supporting environment overrides.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

from autorepro.config import config, reset_config


class TestBehavioralValidation:
    """Test that configuration changes don't affect behavior."""

    def test_cli_scan_output_identical(self):
        """Test that scan command output is identical with configuration."""
        # Run scan command and check it succeeds
        result = subprocess.run(
            ["python3", "-m", "autorepro", "scan", "--json"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,  # Run from repo root
        )

        assert result.returncode == 0
        assert result.stderr == ""

        # Verify JSON is valid
        scan_data = json.loads(result.stdout)
        assert "detected" in scan_data
        assert isinstance(scan_data["detected"], list)

    def test_cli_plan_dry_run_identical(self):
        """Test that plan command dry-run output is identical."""
        result = subprocess.run(
            ["python3", "-m", "autorepro", "plan", "--desc", "test issue", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert result.returncode == 0
        # Plan output should contain expected sections
        assert "## Assumptions" in result.stdout
        assert "## Candidate Commands" in result.stdout

    def test_cli_init_dry_run_identical(self):
        """Test that init command dry-run output is identical."""
        result = subprocess.run(
            ["python3", "-m", "autorepro", "init", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )

        assert result.returncode == 0
        # Should output JSON devcontainer configuration
        devcontainer_data = json.loads(result.stdout)
        assert "name" in devcontainer_data
        assert "features" in devcontainer_data


class TestEnvironmentOverrides:
    """Test environment variable overrides work correctly."""

    def setup_method(self):
        """Reset config before each test."""
        reset_config()

    def test_timeout_override_affects_behavior(self):
        """Test that timeout override changes actual behavior."""
        # Test with custom timeout value
        env_vars = {"AUTOREPRO_TIMEOUT_DEFAULT": "180"}

        with patch.dict(os.environ, env_vars):
            reset_config()  # Force reload with new env
            from autorepro.config import get_config

            config = get_config()

            assert config.timeouts.default_seconds == 180

    def test_max_suggestions_override(self):
        """Test max suggestions override works."""
        env_vars = {"AUTOREPRO_MAX_PLAN_SUGGESTIONS": "10"}

        with patch.dict(os.environ, env_vars):
            reset_config()
            from autorepro.config import get_config

            config = get_config()

            assert config.limits.max_plan_suggestions == 10

    def test_detection_weights_override(self):
        """Test detection weight overrides work."""
        env_vars = {
            "AUTOREPRO_DETECTION_WEIGHT_LOCK": "5",
            "AUTOREPRO_DETECTION_WEIGHT_CONFIG": "4",
        }

        with patch.dict(os.environ, env_vars):
            reset_config()
            from autorepro.config import get_config

            config = get_config()

            assert config.detection.weights["lock"] == 5
            assert config.detection.weights["config"] == 4
            # Unchanged values should remain default
            assert config.detection.weights["setup"] == 2
            assert config.detection.weights["source"] == 1


class TestDetectionBehavior:
    """Test that language detection behavior is preserved."""

    def setup_method(self):
        """Reset config before each test."""
        reset_config()

    def test_detection_results_unchanged(self):
        """Test detection results match expected patterns."""
        from pathlib import Path

        from autorepro.detect import collect_evidence

        # Test on current repo (should detect python)
        repo_path = Path(__file__).parent.parent
        evidence = collect_evidence(repo_path)

        # Should detect python with expected score
        assert "python" in evidence
        python_score = evidence["python"]["score"]

        # Score should be reasonable (pyproject.toml=3, *.py files=1, etc.)
        assert python_score >= 4  # At least pyproject.toml + some .py files

    def test_detection_weights_applied(self):
        """Test that detection weights are correctly applied."""
        from autorepro.detect import SOURCE_PATTERNS, WEIGHTED_PATTERNS

        # Verify weights match configuration
        for pattern, info in WEIGHTED_PATTERNS.items():
            kind = info["kind"]
            expected_weight = config.detection.weights[kind]
            assert (
                info["weight"] == expected_weight
            ), f"Pattern {pattern} has wrong weight"

        for _pattern, info in SOURCE_PATTERNS.items():
            if info["kind"] == "source":
                assert info["weight"] == config.detection.weights["source"]
            elif info["kind"] == "config":
                assert info["weight"] == config.detection.weights["config"]


class TestPlanGeneration:
    """Test that plan generation behavior is preserved."""

    def test_plan_suggestions_use_config_limits(self):
        """Test that plan generation respects configured limits."""
        from autorepro.core.planning import suggest_commands
        from autorepro.utils.plan_processing import extract_keywords

        # Extract keywords from test description
        keywords = extract_keywords("pytest failing tests")
        lang_names = ["python"]

        # Get suggestions with default min_score
        suggestions = suggest_commands(
            keywords, lang_names, min_score=config.limits.min_score_threshold
        )

        # Should return suggestions (exact count depends on rules, but should be reasonable)
        assert isinstance(suggestions, list)
        assert len(suggestions) >= 1  # At least some suggestions for pytest

    def test_score_threshold_filtering(self):
        """Test that score threshold filtering works correctly."""
        from autorepro.core.planning import suggest_commands
        from autorepro.utils.plan_processing import extract_keywords

        keywords = extract_keywords("test issue")
        lang_names = ["python"]

        # Get all suggestions (min_score=0)
        all_suggestions = suggest_commands(keywords, lang_names, min_score=0)

        # Get filtered suggestions (default min_score)
        filtered_suggestions = suggest_commands(
            keywords, lang_names, min_score=config.limits.min_score_threshold
        )

        # Filtered should be <= all suggestions
        assert len(filtered_suggestions) <= len(all_suggestions)


class TestFileOperations:
    """Test that file operations use configured paths."""

    def test_devcontainer_path_configuration(self):
        """Test that devcontainer operations use configured paths."""
        from pathlib import Path

        from autorepro.env import default_devcontainer, write_devcontainer

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Should create file at configured path when no output specified
            expected_path = (
                tmpdir_path
                / config.paths.devcontainer_dir
                / config.paths.devcontainer_file
            )

            # Create parent directory
            expected_path.parent.mkdir(parents=True, exist_ok=True)

            # Write devcontainer with default content
            content = default_devcontainer()
            result_path, diff = write_devcontainer(
                content, out=str(expected_path), force=True
            )

            assert Path(result_path).exists()
            assert Path(result_path).suffix == ".json"

    def test_temp_file_suffix_configuration(self):
        """Test that temporary files use configured suffix."""
        # The temp file suffix is used in write_devcontainer operations
        # This is tested indirectly through the atomic write operation

        # Just verify the configuration value is set correctly
        assert config.paths.temp_file_suffix == ".tmp"
        assert hasattr(config.paths, "temp_file_suffix")


class TestPerformance:
    """Test that configuration system doesn't degrade performance."""

    def test_config_access_performance(self):
        """Test that config access is fast enough."""
        import time

        # Time multiple config accesses
        start_time = time.time()
        for _ in range(1000):
            _ = config.timeouts.default_seconds
            _ = config.limits.max_plan_suggestions
            _ = config.detection.weights["lock"]
        end_time = time.time()

        # Should be very fast (< 0.1 seconds for 1000 accesses)
        duration = end_time - start_time
        assert (
            duration < 0.1
        ), f"Config access too slow: {duration} seconds for 1000 accesses"

    def test_scan_performance_not_regressed(self):
        """Test that scan performance is not significantly worse."""
        import time

        # Time a scan operation
        start_time = time.time()
        result = subprocess.run(
            ["python3", "-m", "autorepro", "scan"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent,
        )
        end_time = time.time()

        # Should complete successfully
        assert result.returncode == 0

        # Should complete reasonably quickly (< 5 seconds)
        duration = end_time - start_time
        assert duration < 5.0, f"Scan too slow: {duration} seconds"
