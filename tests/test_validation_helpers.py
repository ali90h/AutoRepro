"""Tests for validation helper functions."""

from pathlib import Path
from types import SimpleNamespace

from autorepro.utils.validation_helpers import (
    determine_rule_source,
    has_any_keyword_variant,
    has_ci_keywords,
    has_installation_keywords,
    has_test_keywords,
    is_safe_to_write_file,
    needs_pr_update_operation,
    should_apply_repo_relative_path,
)


class TestKeywordValidation:
    """Test keyword validation functions."""

    def test_has_any_keyword_variant(self):
        """Test generic keyword variant checking."""
        keywords = {"pytest", "unittest", "coverage"}
        assert has_any_keyword_variant(keywords, ["test", "testing", "pytest"])
        assert not has_any_keyword_variant(keywords, ["npm", "yarn", "node"])
        assert not has_any_keyword_variant(set(), ["test"])

    def test_has_test_keywords(self):
        """Test test-related keyword detection."""
        assert has_test_keywords({"test", "python"})
        assert has_test_keywords({"tests", "framework"})
        assert has_test_keywords({"testing", "unit"})
        assert not has_test_keywords({"python", "framework"})
        assert not has_test_keywords(set())

    def test_has_installation_keywords(self):
        """Test installation-related keyword detection."""
        assert has_installation_keywords({"install", "dependencies"})
        assert has_installation_keywords({"setup", "configure"})
        assert not has_installation_keywords({"test", "run"})
        assert not has_installation_keywords(set())

    def test_has_ci_keywords(self):
        """Test CI-related keyword detection."""
        assert has_ci_keywords({"ci", "build"})
        assert not has_ci_keywords({"test", "install"})
        assert not has_ci_keywords(set())


class TestRuleSourceDetermination:
    """Test rule source determination logic."""

    def test_determine_rule_source_builtin(self):
        """Test builtin rule detection."""
        rule = SimpleNamespace(cmd="pytest")
        builtin_rules = {"python": [rule]}

        result = determine_rule_source("python", rule, builtin_rules)
        assert result == "builtin"

    def test_determine_rule_source_plugin(self):
        """Test plugin rule detection."""
        rule = SimpleNamespace(cmd="custom-test")
        builtin_rules = {"python": []}

        result = determine_rule_source("python", rule, builtin_rules)
        assert result == "plugin"

    def test_determine_rule_source_missing_ecosystem(self):
        """Test rule source when ecosystem not in builtin_rules."""
        rule = SimpleNamespace(cmd="test")
        builtin_rules = {"other": []}

        result = determine_rule_source("python", rule, builtin_rules)
        assert result == "plugin"


class TestPathLogic:
    """Test path-related validation logic."""

    def test_should_apply_repo_relative_path(self):
        """Test repo-relative path logic."""
        repo_path = Path("/home/user/repo")

        # Should apply: has repo, relative path, not stdout
        assert should_apply_repo_relative_path(repo_path, "output.txt", False)

        # Should not apply: no repo path
        assert not should_apply_repo_relative_path(None, "output.txt", False)

        # Should not apply: absolute path
        assert not should_apply_repo_relative_path(repo_path, "/abs/output.txt", False)

        # Should not apply: stdout output
        assert not should_apply_repo_relative_path(repo_path, "output.txt", True)


class TestPROperations:
    """Test PR operation validation logic."""

    def test_needs_pr_update_operation_true_cases(self):
        """Test cases where PR update is needed."""
        configs = [
            {
                "update_if_exists": True,
                "comment": False,
                "update_pr_body": False,
                "add_labels": False,
                "link_issue": False,
            },
            {
                "update_if_exists": False,
                "comment": True,
                "update_pr_body": False,
                "add_labels": False,
                "link_issue": False,
            },
            {
                "update_if_exists": False,
                "comment": False,
                "update_pr_body": True,
                "add_labels": False,
                "link_issue": False,
            },
            {
                "update_if_exists": False,
                "comment": False,
                "update_pr_body": False,
                "add_labels": True,
                "link_issue": False,
            },
            {
                "update_if_exists": False,
                "comment": False,
                "update_pr_body": False,
                "add_labels": False,
                "link_issue": True,
            },
        ]

        for config in configs:
            pr_config = SimpleNamespace(**config)
            assert needs_pr_update_operation(pr_config), f"Should be True for {config}"

    def test_needs_pr_update_operation_false_case(self):
        """Test case where no PR update is needed."""
        pr_config = SimpleNamespace(
            update_if_exists=False,
            comment=False,
            update_pr_body=False,
            add_labels=False,
            link_issue=False,
        )

        assert not needs_pr_update_operation(pr_config)


class TestFileSafety:
    """Test file write safety validation."""

    def test_is_safe_to_write_file_stdout(self):
        """Test stdout case - always safe."""
        assert is_safe_to_write_file(True, "/some/path", False)
        assert is_safe_to_write_file(True, "/some/path", True)

    def test_is_safe_to_write_file_no_path(self):
        """Test empty path case."""
        assert is_safe_to_write_file(False, "", False)
        assert is_safe_to_write_file(False, None, False)

    def test_is_safe_to_write_file_directory(self, tmp_path):
        """Test directory path case."""
        assert not is_safe_to_write_file(False, str(tmp_path), False)

    def test_is_safe_to_write_file_existing_no_force(self, tmp_path):
        """Test existing file without force."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        assert not is_safe_to_write_file(False, str(test_file), False)
        assert is_safe_to_write_file(False, str(test_file), True)  # With force

    def test_is_safe_to_write_file_new_file(self, tmp_path):
        """Test new file case."""
        new_file = tmp_path / "new.txt"
        assert is_safe_to_write_file(False, str(new_file), False)
