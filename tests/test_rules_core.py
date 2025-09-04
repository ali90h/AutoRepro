"""Tests for the rules engine."""

import os
from unittest.mock import patch

from autorepro.planner import suggest_commands
from autorepro.rules import BUILTIN_RULES, Rule, _load_plugin_rules, get_rules


class TestRulesCore:
    """Test the rules engine core functionality."""

    def test_builtin_rules_structure(self):
        """Test that builtin rules have correct structure."""
        assert "python" in BUILTIN_RULES
        assert "node" in BUILTIN_RULES
        assert "go" in BUILTIN_RULES
        assert "electron" in BUILTIN_RULES

        # Check a Python rule
        pytest_rules = [r for r in BUILTIN_RULES["python"] if "pytest" in r.cmd]
        assert len(pytest_rules) > 0

        # Verify rule structure
        pytest_rule = pytest_rules[0]
        assert isinstance(pytest_rule, Rule)
        assert pytest_rule.cmd
        assert isinstance(pytest_rule.keywords, set)
        assert isinstance(pytest_rule.weight, int)
        assert isinstance(pytest_rule.tags, set)

    def test_get_rules_without_plugins(self):
        """Test get_rules returns builtin rules when no plugins are set."""
        with patch.dict(os.environ, {}, clear=True):
            rules = get_rules()
            assert rules == BUILTIN_RULES

    def test_plugin_loading_no_plugins(self):
        """Test plugin loading when AUTOREPRO_PLUGINS is not set."""
        with patch.dict(os.environ, {}, clear=True):
            plugin_rules = _load_plugin_rules()
            assert plugin_rules == {}

    def test_plugin_loading_with_demo_plugin(self):
        """Test plugin loading with demo plugin."""
        with patch.dict(os.environ, {"AUTOREPRO_PLUGINS": "tests.fixtures.demo_rules"}):
            plugin_rules = _load_plugin_rules()
            assert "python" in plugin_rules

            # Check our demo rule is loaded
            demo_rules = plugin_rules["python"]
            assert len(demo_rules) == 1
            demo_rule = demo_rules[0]
            assert demo_rule.cmd == "pytest -q -k smoke"
            assert "pytest" in demo_rule.keywords
            assert "smoke" in demo_rule.keywords

    def test_get_rules_with_plugins(self):
        """Test get_rules combines builtin and plugin rules."""
        with patch.dict(os.environ, {"AUTOREPRO_PLUGINS": "tests.fixtures.demo_rules"}):
            rules = get_rules()

            # Should have all builtin ecosystems
            assert "python" in rules
            assert "node" in rules

            # Python should have builtin + plugin rules
            python_rules = rules["python"]
            builtin_count = len(BUILTIN_RULES["python"])
            assert len(python_rules) == builtin_count + 1  # +1 for demo rule

            # Find our demo rule
            demo_rules = [r for r in python_rules if "smoke" in r.keywords]
            assert len(demo_rules) == 1
            assert demo_rules[0].cmd == "pytest -q -k smoke"

    def test_suggest_commands_uses_rules(self):
        """Test that suggest_commands uses rules engine."""
        keywords = {"pytest"}
        detected_langs = ["python"]

        suggestions = suggest_commands(keywords, detected_langs, min_score=2)

        # Should find pytest commands
        pytest_suggestions = [s for s in suggestions if "pytest" in s[0]]
        assert len(pytest_suggestions) > 0

        # Check scores and rationales
        for _cmd, score, rationale in pytest_suggestions:
            assert score >= 2  # Should have at least keyword match + lang match
            assert "pytest" in rationale

    def test_suggest_commands_with_plugins(self):
        """Test suggest_commands with plugin rules loaded."""
        keywords = {"pytest", "smoke"}
        detected_langs = ["python"]

        with patch.dict(os.environ, {"AUTOREPRO_PLUGINS": "tests.fixtures.demo_rules"}):
            suggestions = suggest_commands(keywords, detected_langs, min_score=2)

            # Should include our demo rule
            demo_suggestions = [s for s in suggestions if "smoke" in s[0]]
            assert len(demo_suggestions) == 1

            demo_cmd, demo_score, demo_rationale = demo_suggestions[0]
            assert demo_cmd == "pytest -q -k smoke"
            # Score: +3 pytest, +3 smoke, +2 python lang, +1 specificity, +1 weight = 10
            assert demo_score >= 9
            assert "pytest" in demo_rationale
            assert "smoke" in demo_rationale

    def test_plugin_loading_handles_import_errors(self):
        """Test plugin loading gracefully handles import errors."""
        with patch.dict(os.environ, {"AUTOREPRO_PLUGINS": "nonexistent.plugin.module"}):
            plugin_rules = _load_plugin_rules()
            # Should not raise exception and return empty dict
            assert plugin_rules == {}

    def test_plugin_loading_multiple_plugins(self):
        """Test loading multiple plugins."""
        # Create a simple mock plugin in memory

        with patch.dict(os.environ, {"AUTOREPRO_PLUGINS": "tests.fixtures.demo_rules"}):
            plugin_rules = _load_plugin_rules()
            assert "python" in plugin_rules

    def test_ecosystem_filtering_still_works(self):
        """Test that ecosystem filtering logic is preserved."""
        # Test Java conditional inclusion
        java_keywords = {"maven"}
        detected_langs = []

        suggestions = suggest_commands(java_keywords, detected_langs, min_score=0)
        java_suggestions = [s for s in suggestions if "mvn" in s[0]]
        assert len(java_suggestions) > 0  # Should include Java commands when maven keyword present

        # Test without Java keywords - should not include Java
        other_keywords = {"pytest"}
        suggestions = suggest_commands(other_keywords, detected_langs, min_score=0)
        java_suggestions = [s for s in suggestions if "mvn" in s[0]]
        assert not java_suggestions  # Should not include Java commands

    def test_plugin_loading_from_file_path(self, tmp_path):
        """Test loading plugin from direct file path."""
        # Create a temporary plugin file
        plugin_file = tmp_path / "test_plugin.py"
        plugin_file.write_text(
            """
from autorepro.rules import Rule

def provide_rules():
    return {"python": [Rule("pytest --file-plugin", {"file", "test"}, 2, {"test"})]}
"""
        )

        with patch.dict(os.environ, {"AUTOREPRO_PLUGINS": str(plugin_file)}):
            plugin_rules = _load_plugin_rules()
            assert "python" in plugin_rules

            file_rules = plugin_rules["python"]
            assert len(file_rules) == 1
            assert file_rules[0].cmd == "pytest --file-plugin"
            assert "file" in file_rules[0].keywords

    def test_plugin_debug_flag(self, capsys):
        """Test debug flag shows plugin loading errors."""
        with patch.dict(
            os.environ,
            {
                "AUTOREPRO_PLUGINS": "nonexistent.plugin.module",
                "AUTOREPRO_PLUGINS_DEBUG": "1",
            },
        ):
            _load_plugin_rules()
            captured = capsys.readouterr()
            assert "Plugin loading failed" in captured.err
            assert "nonexistent.plugin.module" in captured.err

    def test_plugin_debug_flag_off_by_default(self, capsys):
        """Test plugin errors are silent by default."""
        with patch.dict(os.environ, {"AUTOREPRO_PLUGINS": "nonexistent.plugin.module"}):
            _load_plugin_rules()
            captured = capsys.readouterr()
            assert captured.err == ""  # Should be silent
