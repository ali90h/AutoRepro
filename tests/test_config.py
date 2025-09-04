"""Tests for configuration system."""

import os
from unittest.mock import patch

import pytest

from autorepro.config import AutoReproConfig, get_config, reset_config
from autorepro.config.models import (
    DetectionConfig,
    ExecutableConfig,
    ExitCodeConfig,
    FileConfig,
    LimitsConfig,
    PathConfig,
    TimeoutConfig,
)


class TestTimeoutConfig:
    """Test timeout configuration."""

    def test_default_values(self):
        """Test default timeout values match originals."""
        config = TimeoutConfig()
        assert config.default_seconds == 120

    def test_from_env(self):
        """Test environment variable override."""
        with patch.dict(os.environ, {"AUTOREPRO_TIMEOUT_DEFAULT": "180"}):
            config = TimeoutConfig.from_env()
            assert config.default_seconds == 180


class TestLimitsConfig:
    """Test limits configuration."""

    def test_default_values(self):
        """Test default limit values match originals."""
        config = LimitsConfig()
        assert config.max_plan_suggestions == 5
        assert config.min_score_threshold == 2
        assert config.max_display_length == 80

    def test_from_env(self):
        """Test environment variable overrides."""
        env_vars = {
            "AUTOREPRO_MAX_PLAN_SUGGESTIONS": "10",
            "AUTOREPRO_MIN_SCORE_THRESHOLD": "3",
            "AUTOREPRO_MAX_DISPLAY_LENGTH": "100",
        }
        with patch.dict(os.environ, env_vars):
            config = LimitsConfig.from_env()
            assert config.max_plan_suggestions == 10
            assert config.min_score_threshold == 3
            assert config.max_display_length == 100


class TestPathConfig:
    """Test path configuration."""

    def test_default_values(self):
        """Test default path values match originals."""
        config = PathConfig()
        assert config.devcontainer_dir == ".devcontainer"
        assert config.devcontainer_file == "devcontainer.json"
        assert config.default_plan_file == "repro.md"
        assert config.temp_file_suffix == ".tmp"

    def test_from_env(self):
        """Test environment variable overrides."""
        env_vars = {
            "AUTOREPRO_DEVCONTAINER_DIR": ".container",
            "AUTOREPRO_DEFAULT_PLAN_FILE": "plan.md",
        }
        with patch.dict(os.environ, env_vars):
            config = PathConfig.from_env()
            assert config.devcontainer_dir == ".container"
            assert config.default_plan_file == "plan.md"


class TestDetectionConfig:
    """Test detection configuration."""

    def test_default_values(self):
        """Test default detection weights match originals."""
        config = DetectionConfig()
        assert config.weights["lock"] == 4
        assert config.weights["config"] == 3
        assert config.weights["setup"] == 2
        assert config.weights["source"] == 1

    def test_from_env(self):
        """Test environment variable overrides."""
        env_vars = {
            "AUTOREPRO_DETECTION_WEIGHT_LOCK": "5",
            "AUTOREPRO_DETECTION_WEIGHT_CONFIG": "4",
        }
        with patch.dict(os.environ, env_vars):
            config = DetectionConfig.from_env()
            assert config.weights["lock"] == 5
            assert config.weights["config"] == 4
            assert config.weights["setup"] == 2  # Unchanged


class TestExitCodeConfig:
    """Test exit code configuration."""

    def test_default_values(self):
        """Test default exit codes match originals."""
        config = ExitCodeConfig()
        assert config.success == 0
        assert config.error == 1
        assert config.invalid_args == 2


class TestFileConfig:
    """Test file configuration."""

    def test_default_values(self):
        """Test default file values match originals."""
        config = FileConfig()
        assert config.python_extension == ".py"
        assert config.json_extension == ".json"
        assert config.markdown_extension == ".md"
        assert config.default_format == "md"
        assert config.supported_formats == ("md", "json")


class TestExecutableConfig:
    """Test executable configuration."""

    def test_default_values(self):
        """Test default executable names match originals."""
        config = ExecutableConfig()
        assert config.python_names == ("python3", "python")


class TestAutoReproConfig:
    """Test main configuration container."""

    def test_default_values(self):
        """Test all sub-configurations have correct defaults."""
        config = AutoReproConfig()

        # Verify sub-config types
        assert isinstance(config.timeouts, TimeoutConfig)
        assert isinstance(config.limits, LimitsConfig)
        assert isinstance(config.paths, PathConfig)
        assert isinstance(config.detection, DetectionConfig)
        assert isinstance(config.exit_codes, ExitCodeConfig)
        assert isinstance(config.files, FileConfig)
        assert isinstance(config.executables, ExecutableConfig)

        # Spot check key values
        assert config.timeouts.default_seconds == 120
        assert config.limits.max_plan_suggestions == 5
        assert config.detection.weights["lock"] == 4

    def test_validation_passes_with_defaults(self):
        """Test validation passes with default values."""
        config = AutoReproConfig()
        config.validate()  # Should not raise

    def test_validation_fails_with_invalid_timeout(self):
        """Test validation fails with invalid timeout."""
        config = AutoReproConfig()
        config.timeouts.default_seconds = -1

        with pytest.raises(ValueError, match="Timeout must be positive"):
            config.validate()

    def test_validation_fails_with_invalid_max_suggestions(self):
        """Test validation fails with invalid max suggestions."""
        config = AutoReproConfig()
        config.limits.max_plan_suggestions = 0

        with pytest.raises(ValueError, match="Max plan suggestions must be positive"):
            config.validate()

    def test_validation_fails_with_negative_min_score(self):
        """Test validation fails with negative min score."""
        config = AutoReproConfig()
        config.limits.min_score_threshold = -1

        with pytest.raises(ValueError, match="Min score threshold must be non-negative"):
            config.validate()

    def test_validation_fails_with_invalid_format(self):
        """Test validation fails with unsupported default format."""
        config = AutoReproConfig()
        config.files.default_format = "xml"

        with pytest.raises(ValueError, match="Default format 'xml' not in supported formats"):
            config.validate()


class TestGlobalConfig:
    """Test global configuration functions."""

    def setup_method(self):
        """Reset config before each test."""
        reset_config()

    def test_get_config_returns_same_instance(self):
        """Test get_config returns same instance on multiple calls."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_get_config_creates_valid_config(self):
        """Test get_config creates valid configuration."""
        config = get_config()
        assert isinstance(config, AutoReproConfig)
        config.validate()  # Should not raise

    def test_reset_config_clears_instance(self):
        """Test reset_config allows new instance creation."""
        config1 = get_config()
        reset_config()
        config2 = get_config()
        assert config1 is not config2


class TestConfigurationReplacement:
    """Test that configuration system maintains identical behavior."""

    def setup_method(self):
        """Reset config before each test."""
        reset_config()

    def test_timeout_value_matches_original(self):
        """Test timeout configuration matches original hard-coded value."""
        config = get_config()
        assert config.timeouts.default_seconds == 120

    def test_max_commands_matches_original(self):
        """Test max commands configuration matches original."""
        config = get_config()
        assert config.limits.max_plan_suggestions == 5

    def test_min_score_matches_original(self):
        """Test min score configuration matches original."""
        config = get_config()
        assert config.limits.min_score_threshold == 2

    def test_detection_weights_match_original(self):
        """Test detection weights match original hard-coded values."""
        config = get_config()

        # These should match the weights in detect.py
        assert config.detection.weights["lock"] == 4
        assert config.detection.weights["config"] == 3
        assert config.detection.weights["setup"] == 2
        assert config.detection.weights["source"] == 1

    def test_file_paths_match_original(self):
        """Test file paths match original hard-coded values."""
        config = get_config()
        assert config.paths.devcontainer_dir == ".devcontainer"
        assert config.paths.default_plan_file == "repro.md"

    def test_exit_codes_match_original(self):
        """Test exit codes match original hard-coded values."""
        config = get_config()
        assert config.exit_codes.success == 0
        assert config.exit_codes.error == 1
        assert config.exit_codes.invalid_args == 2
