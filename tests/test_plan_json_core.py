"""Tests for the AutoRepro planner JSON core functionality."""

from autorepro.planner import build_repro_json


class TestBuildReproJsonStructure:
    """Test build_repro_json function structure and types."""

    def test_returns_dict_with_exact_keys(self):
        """Test that build_repro_json returns dict with exact required keys."""
        title = "Test Issue"
        assumptions = ["Test assumption"]
        commands = [("pytest -q", 6, "matched keywords: pytest; detected langs: python")]
        needs = ["Python 3.11+"]
        next_steps = ["Run the command"]

        result = build_repro_json(title, assumptions, commands, needs, next_steps)

        # Check it's a dict
        assert isinstance(result, dict)

        # Check exact keys in exact order
        expected_keys = [
            "schema_version",
            "tool",
            "tool_version",
            "title",
            "assumptions",
            "needs",
            "commands",
            "next_steps",
        ]
        assert list(result.keys()) == expected_keys

        # Check types
        assert isinstance(result["title"], str)
        assert isinstance(result["assumptions"], list)
        assert isinstance(result["needs"], dict)
        assert isinstance(result["commands"], list)
        assert isinstance(result["next_steps"], list)

    def test_key_order_is_stable(self):
        """Test that key order is deterministic and stable."""
        result1 = build_repro_json("Test", ["A"], [("cmd", 1, "reason")], ["need"], ["step"])
        result2 = build_repro_json("Test", ["A"], [("cmd", 1, "reason")], ["need"], ["step"])

        # Keys should be in same order both times
        assert list(result1.keys()) == list(result2.keys())

        # Top-level key order
        expected_keys = [
            "schema_version",
            "tool",
            "tool_version",
            "title",
            "assumptions",
            "needs",
            "commands",
            "next_steps",
        ]
        assert list(result1.keys()) == expected_keys

    def test_commands_have_correct_structure(self):
        """Test that command objects have the correct structure and key order."""
        commands = [
            ("pytest -q", 6, "matched keywords: pytest; detected langs: python"),
            ("npm test", 4, "matched keywords: npm test; bonuses: direct (+3)"),
        ]

        result = build_repro_json("Test", [], commands, [], [])

        assert len(result["commands"]) == 2

        # Check command structure and key order
        for cmd_obj in result["commands"]:
            expected_cmd_keys = ["cmd", "score", "rationale", "matched_keywords", "matched_langs"]
            assert list(cmd_obj.keys()) == expected_cmd_keys

            assert isinstance(cmd_obj["cmd"], str)
            assert isinstance(cmd_obj["score"], int)
            assert isinstance(cmd_obj["rationale"], str)
            assert isinstance(cmd_obj["matched_keywords"], list)
            assert isinstance(cmd_obj["matched_langs"], list)


class TestBuildReproJsonDevcontainer:
    """Test devcontainer presence detection in needs field."""

    def test_devcontainer_present_detection(self):
        """Test that devcontainer present is correctly detected."""
        needs = ["Python 3.11+", "devcontainer: present", "Node.js"]

        result = build_repro_json("Test", [], [], needs, [])

        assert result["needs"]["devcontainer_present"] is True

    def test_devcontainer_absent_when_not_mentioned(self):
        """Test that devcontainer absent when not mentioned in needs."""
        needs = ["Python 3.11+", "Node.js"]

        result = build_repro_json("Test", [], [], needs, [])

        assert result["needs"]["devcontainer_present"] is False

    def test_devcontainer_case_insensitive_detection(self):
        """Test case insensitive devcontainer detection."""
        needs = ["Devcontainer: Present", "DEVCONTAINER: PRESENT"]

        result = build_repro_json("Test", [], [], needs, [])

        assert result["needs"]["devcontainer_present"] is True


class TestBuildReproJsonCommandParsing:
    """Test parsing of matched keywords and languages from rationales."""

    def test_matched_keywords_parsing(self):
        """Test that matched keywords are correctly parsed from rationale."""
        commands = [
            ("pytest -q", 6, "matched keywords: pytest; detected langs: python"),
            ("npm test", 4, "matched keywords: npm, test; bonuses: direct (+3)"),
        ]

        result = build_repro_json("Test", [], commands, [], [])

        # First command
        cmd1 = result["commands"][0]
        assert cmd1["matched_keywords"] == ["pytest"]

        # Second command
        cmd2 = result["commands"][1]
        assert set(cmd2["matched_keywords"]) == {"npm", "test"}

    def test_matched_langs_parsing(self):
        """Test that matched languages are correctly parsed from rationale."""
        commands = [
            ("pytest -q", 6, "matched keywords: pytest; detected langs: python; bonuses: (+5)"),
            ("go test", 4, "detected langs: go, golang; bonuses: lang (+2)"),
        ]

        result = build_repro_json("Test", [], commands, [], [])

        # First command
        cmd1 = result["commands"][0]
        assert cmd1["matched_langs"] == ["python"]

        # Second command
        cmd2 = result["commands"][1]
        assert set(cmd2["matched_langs"]) == {"go", "golang"}

    def test_no_matches_results_in_empty_lists(self):
        """Test that commands with no matches have empty keyword/lang lists."""
        commands = [("some command", 1, "no specific matches")]

        result = build_repro_json("Test", [], commands, [], [])

        cmd = result["commands"][0]
        assert cmd["matched_keywords"] == []
        assert cmd["matched_langs"] == []

    def test_special_characters_filtered_from_keywords(self):
        """Test that special characters are filtered from parsed keywords."""
        commands = [
            ("test cmd", 5, "matched keywords: py*test, n@pm; detected langs: py-thon, no_de")
        ]

        result = build_repro_json("Test", [], commands, [], [])

        cmd = result["commands"][0]
        # Should keep alphanumeric, dashes, underscores
        assert "pytest" in cmd["matched_keywords"]  # * filtered
        assert "npm" in cmd["matched_keywords"]  # @ filtered
        assert "py-thon" in cmd["matched_langs"]  # dash kept
        assert "no_de" in cmd["matched_langs"]  # underscore kept


class TestBuildReproJsonCommandOrder:
    """Test command ordering and --max limit behavior."""

    def test_commands_preserve_input_order(self):
        """Test that commands maintain the input order (pre-sorted by score)."""
        # Commands should already be sorted by score descending, then alphabetically
        commands = [
            ("pytest -q", 6, "high score command"),
            ("npm test", 4, "medium score command"),
            ("go test", 4, "medium score command alphabetically after npm"),
            ("basic cmd", 1, "low score command"),
        ]

        result = build_repro_json("Test", [], commands, [], [])

        # Should maintain input order (assumes input is pre-sorted correctly)
        assert result["commands"][0]["cmd"] == "pytest -q"
        assert result["commands"][1]["cmd"] == "npm test"
        assert result["commands"][2]["cmd"] == "go test"
        assert result["commands"][3]["cmd"] == "basic cmd"

    def test_empty_inputs_handled_correctly(self):
        """Test handling of empty inputs."""
        result = build_repro_json("", [], [], [], [])

        assert result["title"] == ""
        assert result["assumptions"] == []
        assert result["needs"] == {"devcontainer_present": False}
        assert result["commands"] == []
        assert result["next_steps"] == []

    def test_deterministic_output(self):
        """Test that output is deterministic across multiple calls."""
        title = "Test"
        assumptions = ["Assumption 1"]
        commands = [("cmd1", 5, "matched keywords: test")]
        needs = ["Need 1"]
        next_steps = ["Step 1"]

        result1 = build_repro_json(title, assumptions, commands, needs, next_steps)
        result2 = build_repro_json(title, assumptions, commands, needs, next_steps)

        assert result1 == result2
