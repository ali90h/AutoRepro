#!/usr/bin/env python3
"""
Test module for configuration validation methods.

Tests custom exceptions, validation methods for all config classes,
and proper error reporting.
"""

from pathlib import Path
from tempfile import NamedTemporaryFile

import pytest

from autorepro.cli import ExecConfig, InitConfig, PlanConfig, PrConfig
from autorepro.config.exceptions import (
    ConfigValidationError,
    CrossFieldValidationError,
    FieldValidationError,
)
from autorepro.io.github import GitHubPRConfig, IssueConfig


class TestCustomExceptions:
    """Test custom exception classes for configuration validation."""

    def test_config_validation_error_base(self):
        """Test ConfigValidationError base exception."""
        error = ConfigValidationError("test message", field="test_field")
        assert str(error) == "test message"
        assert error.field == "test_field"
        assert isinstance(error, ValueError)

    def test_field_validation_error(self):
        """Test FieldValidationError for single field issues."""
        error = FieldValidationError("invalid value", field="timeout")
        assert str(error) == "invalid value"
        assert error.field == "timeout"
        assert isinstance(error, ConfigValidationError)

    def test_cross_field_validation_error(self):
        """Test CrossFieldValidationError for multi-field issues."""
        error = CrossFieldValidationError("mutual exclusion", field="desc,file")
        assert str(error) == "mutual exclusion"
        assert error.field == "desc,file"
        assert isinstance(error, ConfigValidationError)


class TestPrConfigValidation:
    """Test PrConfig validation methods."""

    def test_valid_config_passes(self):
        """Test that valid configuration passes validation."""
        config = PrConfig(
            desc="test description",
            title="Test PR",
            body="Test body",
            repo_slug="owner/repo",
            min_score=0,
            format_type="md",
        )
        # Should not raise any exception
        config.validate()

    def test_desc_file_mutual_exclusivity(self):
        """Test that desc and file cannot both be specified."""
        config = PrConfig(
            desc="test description",
            file="test.txt",
            title="Test PR",
            body="Test body",
            repo_slug="owner/repo",
        )

        with pytest.raises(CrossFieldValidationError) as exc_info:
            config.validate()
        assert "Cannot specify both --desc and --file" in str(exc_info.value)
        assert exc_info.value.field == "desc,file"

    def test_desc_file_required(self):
        """Test that either desc or file must be specified."""
        config = PrConfig(title="Test PR", body="Test body", repo_slug="owner/repo")

        with pytest.raises(CrossFieldValidationError) as exc_info:
            config.validate()
        assert "Must specify either --desc or --file" in str(exc_info.value)
        assert exc_info.value.field == "desc,file"

    def test_negative_min_score(self):
        """Test that min_score cannot be negative."""
        config = PrConfig(
            desc="test description",
            title="Test PR",
            body="Test body",
            repo_slug="owner/repo",
            min_score=-1,
        )

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "min_score must be non-negative" in str(exc_info.value)
        assert exc_info.value.field == "min_score"

    def test_invalid_format_type(self):
        """Test that format_type must be valid."""
        config = PrConfig(
            desc="test description",
            title="Test PR",
            body="Test body",
            repo_slug="owner/repo",
            format_type="invalid",
        )

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "format_type must be 'md' or 'json'" in str(exc_info.value)
        assert exc_info.value.field == "format_type"

    def test_invalid_repo_slug_format(self):
        """Test that repo_slug must follow owner/repo format."""
        config = PrConfig(
            desc="test description", title="Test PR", body="Test body", repo_slug="invalid-slug"
        )

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "repo_slug must be in format" in str(exc_info.value)
        assert exc_info.value.field == "repo_slug"


class TestExecConfigValidation:
    """Test ExecConfig validation methods."""

    def test_valid_config_passes(self):
        """Test that valid configuration passes validation."""
        config = ExecConfig(desc="test description", timeout=30, index=0)
        # Should not raise any exception
        config.validate()

    def test_desc_file_mutual_exclusivity(self):
        """Test that desc and file cannot both be specified."""
        config = ExecConfig(desc="test description", file="test.txt")

        with pytest.raises(CrossFieldValidationError) as exc_info:
            config.validate()
        assert "Cannot specify both --desc and --file" in str(exc_info.value)
        assert exc_info.value.field == "desc,file"

    def test_desc_file_required(self):
        """Test that either desc or file must be specified."""
        config = ExecConfig()

        with pytest.raises(CrossFieldValidationError) as exc_info:
            config.validate()
        assert "Must specify either --desc or --file" in str(exc_info.value)
        assert exc_info.value.field == "desc,file"

    def test_invalid_timeout(self):
        """Test that timeout must be positive."""
        config = ExecConfig(desc="test description", timeout=0)

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "timeout must be positive" in str(exc_info.value)
        assert exc_info.value.field == "timeout"

    def test_negative_index(self):
        """Test that index cannot be negative."""
        config = ExecConfig(desc="test description", index=-1)

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "index must be non-negative" in str(exc_info.value)
        assert exc_info.value.field == "index"

    def test_nonexistent_env_file(self):
        """Test that env_file must exist if specified."""
        config = ExecConfig(desc="test description", env_file="/nonexistent/file.env")

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "env_file does not exist" in str(exc_info.value)
        assert exc_info.value.field == "env_file"


class TestInitConfigValidation:
    """Test InitConfig validation methods."""

    def test_valid_config_passes(self):
        """Test that valid configuration passes validation."""
        config = InitConfig(force=True, dry_run=False)
        # Should not raise any exception
        config.validate()

    def test_nonexistent_repo_path(self):
        """Test that repo_path must exist if specified."""
        config = InitConfig(repo_path=Path("/nonexistent/path"))

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "repo_path does not exist" in str(exc_info.value)
        assert exc_info.value.field == "repo_path"

    def test_repo_path_not_directory(self):
        """Test that repo_path must be a directory."""
        with NamedTemporaryFile() as temp_file:
            config = InitConfig(repo_path=Path(temp_file.name))

            with pytest.raises(FieldValidationError) as exc_info:
                config.validate()
            assert "repo_path must be a directory" in str(exc_info.value)
            assert exc_info.value.field == "repo_path"


class TestPlanConfigValidation:
    """Test PlanConfig validation methods."""

    def test_valid_config_passes(self):
        """Test that valid configuration passes validation."""
        config = PlanConfig(
            desc="test description",
            file=None,
            out="output.md",
            force=False,
            max_commands=5,
            format_type="md",
            dry_run=False,
            repo=None,
            strict=False,
            min_score=0,
        )
        # Should not raise any exception
        config.validate()

    def test_desc_file_mutual_exclusivity(self):
        """Test that desc and file cannot both be specified."""
        config = PlanConfig(
            desc="test description",
            file="test.txt",
            out="output.md",
            force=False,
            max_commands=5,
            format_type="md",
            dry_run=False,
            repo=None,
            strict=False,
            min_score=0,
        )

        with pytest.raises(CrossFieldValidationError) as exc_info:
            config.validate()
        assert "Cannot specify both --desc and --file" in str(exc_info.value)
        assert exc_info.value.field == "desc,file"

    def test_desc_file_required(self):
        """Test that either desc or file must be specified."""
        config = PlanConfig(
            desc=None,
            file=None,
            out="output.md",
            force=False,
            max_commands=5,
            format_type="md",
            dry_run=False,
            repo=None,
            strict=False,
            min_score=0,
        )

        with pytest.raises(CrossFieldValidationError) as exc_info:
            config.validate()
        assert "Must specify either --desc or --file" in str(exc_info.value)
        assert exc_info.value.field == "desc,file"

    def test_invalid_max_commands(self):
        """Test that max_commands must be positive."""
        config = PlanConfig(
            desc="test description",
            file=None,
            out="output.md",
            force=False,
            max_commands=0,
            format_type="md",
            dry_run=False,
            repo=None,
            strict=False,
            min_score=0,
        )

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "max_commands must be positive" in str(exc_info.value)
        assert exc_info.value.field == "max_commands"

    def test_negative_min_score(self):
        """Test that min_score cannot be negative."""
        config = PlanConfig(
            desc="test description",
            file=None,
            out="output.md",
            force=False,
            max_commands=5,
            format_type="md",
            dry_run=False,
            repo=None,
            strict=False,
            min_score=-1,
        )

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "min_score must be non-negative" in str(exc_info.value)
        assert exc_info.value.field == "min_score"

    def test_invalid_format_type(self):
        """Test that format_type must be valid."""
        config = PlanConfig(
            desc="test description",
            file=None,
            out="output.md",
            force=False,
            max_commands=5,
            format_type="invalid",
            dry_run=False,
            repo=None,
            strict=False,
            min_score=0,
        )

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "format_type must be one of" in str(exc_info.value)
        assert exc_info.value.field == "format_type"

    def test_nonexistent_file(self):
        """Test that file must exist if specified."""
        config = PlanConfig(
            desc=None,
            file="/nonexistent/file.txt",
            out="output.md",
            force=False,
            max_commands=5,
            format_type="md",
            dry_run=False,
            repo=None,
            strict=False,
            min_score=0,
        )

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "file does not exist" in str(exc_info.value)
        assert exc_info.value.field == "file"


class TestGitHubPRConfigValidation:
    """Test GitHubPRConfig validation methods."""

    def test_valid_config_passes(self):
        """Test that valid configuration passes validation."""
        config = GitHubPRConfig(
            title="Test PR", body="Test body", base_branch="main", head_branch="feature-branch"
        )
        # Should not raise any exception
        config.validate()

    def test_empty_title(self):
        """Test that title cannot be empty."""
        config = GitHubPRConfig(title="", body="Test body")

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "title cannot be empty" in str(exc_info.value)
        assert exc_info.value.field == "title"

    def test_whitespace_only_title(self):
        """Test that title cannot be whitespace-only."""
        config = GitHubPRConfig(title="   ", body="Test body")

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "title cannot be empty or whitespace-only" in str(exc_info.value)
        assert exc_info.value.field == "title"

    def test_empty_base_branch(self):
        """Test that base_branch cannot be empty."""
        config = GitHubPRConfig(title="Test PR", body="Test body", base_branch="")

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "base_branch cannot be empty" in str(exc_info.value)
        assert exc_info.value.field == "base_branch"

    def test_invalid_base_branch_characters(self):
        """Test that base_branch cannot contain invalid characters."""
        invalid_branches = [
            "branch name",
            "branch~1",
            "branch^",
            "branch:",
            "branch?",
            "branch*",
            "branch[test]",
            "branch\\test",
        ]

        for invalid_branch in invalid_branches:
            config = GitHubPRConfig(title="Test PR", body="Test body", base_branch=invalid_branch)

            with pytest.raises(FieldValidationError) as exc_info:
                config.validate()
            assert "base_branch contains invalid character" in str(exc_info.value)
            assert exc_info.value.field == "base_branch"

    def test_empty_head_branch(self):
        """Test that head_branch cannot be empty if specified."""
        config = GitHubPRConfig(title="Test PR", body="Test body", head_branch="")

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "head_branch cannot be empty" in str(exc_info.value)
        assert exc_info.value.field == "head_branch"

    def test_invalid_head_branch_characters(self):
        """Test that head_branch cannot contain invalid characters."""
        config = GitHubPRConfig(title="Test PR", body="Test body", head_branch="branch name")

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "head_branch contains invalid character" in str(exc_info.value)
        assert exc_info.value.field == "head_branch"


class TestIssueConfigValidation:
    """Test IssueConfig validation methods."""

    def test_valid_config_passes(self):
        """Test that valid configuration passes validation."""
        config = IssueConfig(title="Test Issue", body="Test body")
        # Should not raise any exception
        config.validate()

    def test_empty_title(self):
        """Test that title cannot be empty."""
        config = IssueConfig(title="")

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "title cannot be empty" in str(exc_info.value)
        assert exc_info.value.field == "title"

    def test_whitespace_only_title(self):
        """Test that title cannot be whitespace-only."""
        config = IssueConfig(title="   ")

        with pytest.raises(FieldValidationError) as exc_info:
            config.validate()
        assert "title cannot be empty or whitespace-only" in str(exc_info.value)
        assert exc_info.value.field == "title"
