"""Tests for the AutoRepro planner core functions (updated for new implementation)."""

from autorepro.planner import (
    build_repro_json,
    build_repro_md,
    extract_keywords,
    normalize,
    safe_truncate_60,
    suggest_commands,
)


class TestNormalize:
    """Test the normalize function."""

    def test_normalize(self):
        """Test normalize with mixed case and odd whitespace."""
        # Input with mixed case, multiple spaces, newlines, and punctuation noise
        input_text = "  PyTest   TESTS\n\nfailing  on   CI    with   `npm`  \n  "
        result = normalize(input_text)

        # Should be lowercase with normalized whitespace
        expected = "pytest tests failing on ci with npm"
        assert result == expected

    def test_normalize_punctuation_removal(self):
        """Test that normalize removes punctuation noise."""
        input_text = "# Tests **failing** with `pytest` and 'jest' <problem>"
        result = normalize(input_text)

        # Should remove # * ` ' < > but keep words
        expected = "tests failing with pytest and jest problem"
        assert result == expected

    def test_normalize_empty_string(self):
        """Test normalize with empty string."""
        result = normalize("")
        assert result == ""

    def test_normalize_whitespace_only(self):
        """Test normalize with whitespace-only string."""
        result = normalize("   \n\t  \n  ")
        assert result == ""


class TestExtractKeywords:
    """Test the extract_keywords function with regex-based implementation."""

    def test_empty_string(self):
        """Test keyword extraction from empty string."""
        result = extract_keywords("")
        assert result == set()

    def test_extract_keywords_basic(self):
        """Test basic keyword extraction with pytest and jest."""
        # Mixed sentence containing both pytest and jest (normalized)
        text = "the pytest tests are failing but jest works fine in our ci"
        result = extract_keywords(text)

        # Should include both pytest and jest
        assert "pytest" in result
        assert "jest" in result

    def test_python_keywords(self):
        """Test extraction of Python-related keywords."""
        text = "pytest tests failing on CI with tox"
        result = extract_keywords(text)
        expected = {"pytest", "tox"}
        assert result == expected

    def test_node_keywords(self):
        """Test extraction of Node.js-related keywords."""
        text = "npm test failing with jest and vitest"
        result = extract_keywords(text)
        expected = {"npm test", "jest", "vitest"}
        assert result == expected

    def test_go_keywords(self):
        """Test extraction of Go-related keywords."""
        text = "go test passing but gotestsum fails"
        result = extract_keywords(text)
        expected = {"go test", "gotestsum"}
        assert result == expected

    def test_electron_keywords(self):
        """Test extraction of Electron-related keywords."""
        text = "electron app shows white screen in main process"
        result = extract_keywords(text)
        expected = {"electron", "white screen", "main process"}
        assert result == expected

    def test_multiword_phrases(self):
        """Test that multi-word phrases are detected correctly."""
        text = "npm test passes but pnpm test fails"
        result = extract_keywords(text)
        expected = {"npm test", "pnpm test"}
        assert result == expected

    def test_case_insensitive(self):
        """Test that extraction is case insensitive."""
        text = "PyTest TESTS failing with NPM TEST"
        normalized = normalize(text)  # Must normalize first for case insensitivity
        result = extract_keywords(normalized)
        expected = {"pytest", "npm test"}
        assert result == expected

    def test_word_boundaries(self):
        """Test that word boundaries prevent false matches."""
        text = "testing with mypytest and anpmtest"
        result = extract_keywords(text)
        # Should not match "pytest" or "npm test" as parts of other words
        assert "pytest" not in result
        assert "npm test" not in result


class TestSuggestCommands:
    """Test the suggest_commands function with new scoring system."""

    def test_python_keyword_matching(self):
        """Test command suggestions for Python keywords with scoring."""
        keywords = {"pytest"}
        detected_langs = ["python"]

        suggestions = suggest_commands(keywords, detected_langs)

        # Should have pytest suggestions at top with high scores
        assert len(suggestions) > 0

        # Find pytest commands
        pytest_commands = [
            (cmd, score, rationale)
            for cmd, score, rationale in suggestions
            if "pytest" in cmd
        ]
        assert len(pytest_commands) > 0

        # Check that pytest -q gets highest score (should be 6: +3 direct, +2 lang, +1 specific)
        pytest_q = next(
            (score for cmd, score, _ in suggestions if cmd == "pytest -q"), None
        )
        assert pytest_q is not None
        assert pytest_q >= 6

    def test_node_keyword_matching(self):
        """Test command suggestions for Node.js keywords."""
        keywords = {"npm test", "jest"}
        detected_langs = ["node"]

        suggestions = suggest_commands(keywords, detected_langs)

        # Should have npm test and jest suggestions
        npm_commands = [cmd for cmd, _, _ in suggestions if "npm test" in cmd]
        jest_commands = [cmd for cmd, _, _ in suggestions if "jest" in cmd]

        assert len(npm_commands) > 0
        assert len(jest_commands) > 0

    def test_language_detection_bonus(self):
        """Test that language detection provides +2 bonus."""
        keywords = set()  # No keywords
        detected_langs = ["python"]

        suggestions = suggest_commands(keywords, detected_langs)

        # Should have Python commands with +2 language bonus
        python_commands = [
            (cmd, score, rationale)
            for cmd, score, rationale in suggestions
            if any(lang in rationale for lang in ["python"])
        ]
        assert len(python_commands) > 0

    def test_specificity_bonus(self):
        """Test that specific commands get +1 bonus."""
        keywords = {"pytest"}
        detected_langs = ["python"]

        suggestions = suggest_commands(keywords, detected_langs)

        # pytest -q should score higher than plain pytest
        pytest_score = next(
            (score for cmd, score, _ in suggestions if cmd == "pytest"), None
        )
        pytest_q_score = next(
            (score for cmd, score, _ in suggestions if cmd == "pytest -q"), None
        )

        if pytest_score is not None and pytest_q_score is not None:
            assert pytest_q_score > pytest_score

    def test_alphabetical_tie_breaking(self):
        """Test that commands with same score are ordered alphabetically."""
        keywords = set()
        detected_langs = ["python", "node"]  # Multiple languages for potential ties

        suggestions = suggest_commands(keywords, detected_langs)

        # Group by score and check alphabetical ordering within groups
        score_groups = {}
        for cmd, score, _ in suggestions:
            if score not in score_groups:
                score_groups[score] = []
            score_groups[score].append(cmd)

        # Check each score group is alphabetically ordered
        for score, commands in score_groups.items():
            assert commands == sorted(commands), (
                f"Commands with score {score} not alphabetically ordered"
            )

    def test_detailed_rationales(self):
        """Test that rationales show matched keywords and detected langs."""
        keywords = {"pytest"}
        detected_langs = ["python"]

        suggestions = suggest_commands(keywords, detected_langs)

        # Find pytest -q command
        pytest_q_rationale = next(
            (rationale for cmd, _, rationale in suggestions if cmd == "pytest -q"), None
        )
        assert pytest_q_rationale is not None
        assert "matched keywords: pytest" in pytest_q_rationale
        assert "detected langs: python" in pytest_q_rationale
        assert "bonuses:" in pytest_q_rationale

    def test_no_suggestions_when_no_matches(self):
        """Test that no suggestions are returned when no keywords or languages match."""
        keywords = set()
        detected_langs = []

        suggestions = suggest_commands(keywords, detected_langs)

        # Should return empty list when no keyword or language matches
        assert not suggestions, f"Expected no suggestions, got: {suggestions}"

    def test_suggest_commands_weighting(self):
        """Test that pytest -q ranks above npx vitest run with correct weighting."""
        keywords = {"pytest", "vitest"}
        detected_langs = ["python"]

        suggestions = suggest_commands(keywords, detected_langs)

        # Find pytest -q and npx vitest run in suggestions
        pytest_q_info = None
        vitest_info = None

        for cmd, score, rationale in suggestions:
            if cmd == "pytest -q":
                pytest_q_info = (cmd, score, rationale)
            elif cmd == "npx vitest run":
                vitest_info = (cmd, score, rationale)

        # Both commands should be present
        assert pytest_q_info is not None, "pytest -q should be in suggestions"
        assert vitest_info is not None, "npx vitest run should be in suggestions"

        # pytest -q should have higher score than npx vitest run
        pytest_score = pytest_q_info[1]
        vitest_score = vitest_info[1]
        assert pytest_score > vitest_score, (
            f"pytest -q (score {pytest_score}) should rank above "
            f"npx vitest run (score {vitest_score})"
        )

        # pytest -q should appear before npx vitest run in the sorted list
        pytest_index = next(
            i for i, (cmd, _, _) in enumerate(suggestions) if cmd == "pytest -q"
        )
        vitest_index = next(
            i for i, (cmd, _, _) in enumerate(suggestions) if cmd == "npx vitest run"
        )
        assert pytest_index < vitest_index, (
            "pytest -q should appear before npx vitest run in sorted results"
        )


class TestSafeTruncate60:
    """Test the safe_truncate_60 helper function."""

    def test_short_text_unchanged(self):
        """Test that short text is returned unchanged."""
        text = "Short title"
        result = safe_truncate_60(text)
        assert result == "Short title"
        assert len(result) <= 60

    def test_exactly_60_chars(self):
        """Test text that is exactly 60 characters."""
        text = "This is exactly sixty characters long and should not be trun"  # Exactly 60 chars
        assert len(text) == 60
        result = safe_truncate_60(text)
        assert result == text
        assert "…" not in result

    def test_over_60_chars_truncated(self):
        """Test that text over 60 characters is truncated with ellipsis."""
        text = (
            "This is definitely longer than sixty characters and should be "
            "truncated with an ellipsis"
        )
        result = safe_truncate_60(text)
        assert len(result) <= 61  # 60 chars + ellipsis
        assert result.endswith("…")
        assert result.startswith(
            "This is definitely longer than sixty characters and should b"
        )

    def test_trailing_whitespace_trimmed(self):
        """Test that trailing whitespace is trimmed before adding ellipsis."""
        text = (
            "This text has trailing spaces and is long enough to need truncation"
            + " " * 30
        )  # Over 60 chars
        result = safe_truncate_60(text)
        assert not result.endswith(" …")  # Should not have space before ellipsis
        assert result.endswith("…")

    def test_empty_string(self):
        """Test empty string handling."""
        result = safe_truncate_60("")
        assert result == ""


class TestBuildReproMd:
    """Test the build_repro_md function with new format."""

    def test_canonical_sections_present(self):
        """Test that all canonical sections are present with correct names."""
        title = "Test Issue"
        result = build_repro_md(title, [], [], [], [])

        # Check canonical section names
        assert "# Test Issue" in result
        assert "## Assumptions" in result
        assert "## Candidate Commands" in result
        assert "## Needed Files/Env" in result
        assert "## Next Steps" in result

    def test_title_truncation(self):
        """Test that long titles are safely truncated."""
        # String exceeding 60 chars to test truncation
        long_title = "This is a very long issue description that is definitely longer than 60 chars"
        result = build_repro_md(long_title, [], [], [], [])

        lines = result.split("\n")
        title_line = lines[0]
        assert title_line.startswith("# ")
        title_text = title_line[2:]  # Remove "# "
        assert len(title_text) <= 61  # 60 chars + potential ellipsis
        assert title_text.endswith("…")

    def test_default_assumptions(self):
        """Test that default assumptions are provided when list is empty."""
        result = build_repro_md("Test", [], [], [], [])

        assert "- OS: Linux (CI runner) — editable" in result
        assert "- Python 3.11 / Node 20 unless otherwise stated" in result
        assert (
            "- Network available for package mirrors; real network tests may be isolated later"
            in result
        )

    def test_custom_assumptions(self):
        """Test that custom assumptions are used when provided."""
        assumptions = ["Custom assumption 1", "Custom assumption 2"]
        result = build_repro_md("Test", assumptions, [], [], [])

        assert "- Custom assumption 1" in result
        assert "- Custom assumption 2" in result
        # Should not have defaults
        assert "OS: Linux (CI runner)" not in result

    def test_line_based_commands(self):
        """Test that commands are rendered as lines, not table."""
        commands = [
            ("pytest -q", 6, "matched: pytest (+3), lang: python (+2), specific (+1)"),
            ("npm test -s", 4, "matched: npm test (+3), specific (+1)"),
        ]
        result = build_repro_md("Test", [], commands, [], [])

        # Should not have table format
        assert "| Score | Command | Why |" not in result
        assert "|-------|---------|-----|" not in result

        # Should have line format
        assert (
            "- `pytest -q` — matched: pytest (+3), lang: python (+2), specific (+1)"
            in result
        )
        assert "- `npm test -s` — matched: npm test (+3), specific (+1)" in result

    def test_command_sorting(self):
        """Test that commands are sorted by score desc, then alphabetically."""
        commands = [
            ("npm test -s", 4, "reason"),
            ("pytest -q", 6, "reason"),
            ("go test", 4, "reason"),  # Same score as npm test, should be alphabetical
        ]
        result = build_repro_md("Test", [], commands, [], [])

        lines = result.split("\n")

        # Find command lines specifically in the Candidate Commands section
        in_commands_section = False
        command_lines = []
        for line in lines:
            if line == "## Candidate Commands":
                in_commands_section = True
                continue
            elif line.startswith("##"):  # Next section
                in_commands_section = False
                continue
            elif in_commands_section and " — " in line and line.strip():
                command_lines.append(line)

        assert len(command_lines) == 3
        assert command_lines[0].startswith("- `pytest -q`")  # Highest score (6)
        assert command_lines[1].startswith(
            "- `go test`"
        )  # Score 4, alphabetically first
        assert command_lines[2].startswith(
            "- `npm test -s`"
        )  # Score 4, alphabetically second

    def test_default_next_steps(self):
        """Test that default next steps are provided when list is empty."""
        result = build_repro_md("Test", [], [], [], [])

        assert "- Run the highest-score command" in result
        assert "- If it fails: switch to the second" in result
        assert "- Record brief logs in report.md" in result

    def test_custom_next_steps(self):
        """Test that custom next steps are used when provided."""
        next_steps = ["Custom step 1", "Custom step 2"]
        result = build_repro_md("Test", [], [], [], next_steps)

        assert "- Custom step 1" in result
        assert "- Custom step 2" in result
        # Should not have defaults
        assert "Run the highest-score command" not in result

    def test_devcontainer_in_needs(self):
        """Test that devcontainer status appears in needs section."""
        needs = ["devcontainer: present", "Python 3.11+"]
        result = build_repro_md("Test", [], [], needs, [])

        assert "- devcontainer: present" in result
        assert "- Python 3.11+" in result

    def test_stable_output_format(self):
        """Test that output format is stable and deterministic."""
        title = "Test"
        assumptions = ["Assumption 1"]
        commands = [("cmd1", 10, "reason1")]
        needs = ["Need 1"]
        next_steps = ["Step 1"]

        # Generate twice to ensure deterministic
        result1 = build_repro_md(title, assumptions, commands, needs, next_steps)
        result2 = build_repro_md(title, assumptions, commands, needs, next_steps)

        assert result1 == result2

        # Check structure
        lines = result1.split("\n")
        assert lines[0] == "# Test"
        assert lines[1] == ""  # Empty line after title
        assert lines[-1] == ""  # Ends with newline

    def test_build_repro_md_structure(self):
        """Test that build_repro_md produces five sections in correct order."""
        # Pass dummy values to build_repro_md
        title = "Test Issue Title"
        assumptions = ["Test assumption"]
        commands = [("test-cmd", 5, "test reason")]
        needs = ["Test requirement"]
        next_steps = ["Test step"]

        result = build_repro_md(title, assumptions, commands, needs, next_steps)

        # Split into lines for analysis
        lines = result.split("\n")

        # Find section headers
        section_indices = {}
        for i, line in enumerate(lines):
            if line.startswith("# "):
                section_indices["title"] = i
            elif line == "## Assumptions":
                section_indices["assumptions"] = i
            elif line == "## Candidate Commands":
                section_indices["commands"] = i
            elif line == "## Needed Files/Env":
                section_indices["needs"] = i
            elif line == "## Next Steps":
                section_indices["next_steps"] = i

        # Assert all five sections exist
        assert "title" in section_indices, "Title section (# ...) not found"
        assert "assumptions" in section_indices, "## Assumptions section not found"
        assert "commands" in section_indices, "## Candidate Commands section not found"
        assert "needs" in section_indices, "## Needed Files/Env section not found"
        assert "next_steps" in section_indices, "## Next Steps section not found"

        # Assert sections are in correct order
        expected_order = ["title", "assumptions", "commands", "needs", "next_steps"]
        actual_order = sorted(section_indices.keys(), key=lambda k: section_indices[k])
        assert actual_order == expected_order, (
            f"Sections not in correct order. Expected {expected_order}, got {actual_order}"
        )

        # Verify section content makes sense
        assert "Test Issue Title" in lines[section_indices["title"]]
        assert any("Test assumption" in line for line in lines), (
            "Assumption content not found"
        )
        assert any("test-cmd" in line for line in lines), "Command content not found"
        assert any("Test requirement" in line for line in lines), (
            "Need content not found"
        )
        assert any("Test step" in line for line in lines), "Next step content not found"


class TestBuildReproJson:
    """Test the build_repro_json function."""

    def test_basic_structure(self):
        """Test that JSON output has the correct basic structure."""
        title = "Test Issue"
        assumptions = ["Test assumption"]
        commands = [
            ("pytest -q", 6, "matched: pytest (+3), lang: python (+2), specific (+1)")
        ]
        needs = ["Python 3.11+"]
        next_steps = ["Run the command"]

        result = build_repro_json(title, assumptions, commands, needs, next_steps)

        # Check all required keys are present in correct order
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

        # Check basic types
        assert isinstance(result["schema_version"], int)
        assert result["schema_version"] == 1
        assert isinstance(result["tool"], str)
        assert result["tool"] == "autorepro"
        assert isinstance(result["tool_version"], str)
        assert isinstance(result["title"], str)
        assert isinstance(result["assumptions"], list)
        assert isinstance(result["needs"], dict)
        assert isinstance(result["commands"], list)
        assert isinstance(result["next_steps"], list)

    def test_devcontainer_detection_present(self):
        """Test that devcontainer present is correctly detected."""
        needs = ["Python 3.11+", "devcontainer: present", "Node.js"]

        result = build_repro_json("Test", [], [], needs, [])

        assert result["needs"]["devcontainer_present"] is True

    def test_devcontainer_detection_absent(self):
        """Test that devcontainer absent is correctly detected."""
        needs = ["Python 3.11+", "Node.js"]

        result = build_repro_json("Test", [], [], needs, [])

        assert result["needs"]["devcontainer_present"] is False

    def test_command_parsing_matched_keywords(self):
        """Test that matched keywords are correctly parsed from rationale."""
        commands = [
            ("pytest -q", 6, "matched keywords: pytest; detected langs: python"),
            ("npm test", 4, "matched keywords: npm test; bonuses: direct (+3)"),
        ]

        result = build_repro_json("Test", [], commands, [], [])

        assert len(result["commands"]) == 2

        # Check first command
        cmd1 = result["commands"][0]
        assert cmd1["cmd"] == "pytest -q"
        assert cmd1["score"] == 6
        assert cmd1["matched_keywords"] == ["pytest"]

        # Check second command
        cmd2 = result["commands"][1]
        assert cmd2["cmd"] == "npm test"
        assert cmd2["score"] == 4
        assert cmd2["matched_keywords"] == ["npm", "test"]

    def test_command_parsing_matched_langs(self):
        """Test that matched languages are correctly parsed from rationale."""
        commands = [
            ("pytest -q", 6, "matched keywords: pytest; detected langs: python"),
            ("go test", 4, "detected langs: go; bonuses: lang: go (+2)"),
        ]

        result = build_repro_json("Test", [], commands, [], [])

        assert len(result["commands"]) == 2

        # Check first command
        cmd1 = result["commands"][0]
        assert cmd1["matched_langs"] == ["python"]

        # Check second command
        cmd2 = result["commands"][1]
        assert cmd2["matched_langs"] == ["go"]

    def test_command_parsing_no_matches(self):
        """Test commands with no keyword or language matches."""
        commands = [("some command", 1, "no specific matches")]

        result = build_repro_json("Test", [], commands, [], [])

        cmd = result["commands"][0]
        assert cmd["matched_keywords"] == []
        assert cmd["matched_langs"] == []

    def test_command_parsing_multiple_keywords(self):
        """Test parsing multiple keywords from rationale."""
        commands = [
            (
                "complex cmd",
                5,
                "matched keywords: pytest, jest; detected langs: python, node",
            ),
        ]

        result = build_repro_json("Test", [], commands, [], [])

        cmd = result["commands"][0]
        assert "pytest" in cmd["matched_keywords"]
        assert "jest" in cmd["matched_keywords"]
        assert "python" in cmd["matched_langs"]
        assert "node" in cmd["matched_langs"]

    def test_command_parsing_special_characters(self):
        """Test that special characters are filtered from parsed keywords."""
        commands = [
            (
                "test cmd",
                5,
                "matched keywords: py*test, n@pm; detected langs: py-thon, no_de",
            ),
        ]

        result = build_repro_json("Test", [], commands, [], [])

        cmd = result["commands"][0]
        # Should keep alphanumeric, dashes, underscores
        assert "pytest" in cmd["matched_keywords"]  # * filtered out
        assert "npm" in cmd["matched_keywords"]  # @ filtered out
        assert "py-thon" in cmd["matched_langs"]  # dash kept
        assert "no_de" in cmd["matched_langs"]  # underscore kept

    def test_empty_inputs(self):
        """Test handling of empty inputs."""
        result = build_repro_json("", [], [], [], [])

        assert result["title"] == ""
        assert result["assumptions"] == []
        assert result["needs"] == {"devcontainer_present": False}
        assert result["commands"] == []
        assert result["next_steps"] == []

    def test_deterministic_output(self):
        """Test that output is deterministic."""
        title = "Test"
        assumptions = ["Assumption 1"]
        commands = [("cmd1", 5, "matched keywords: test; bonuses: direct: test (+3)")]
        needs = ["Need 1"]
        next_steps = ["Step 1"]

        result1 = build_repro_json(title, assumptions, commands, needs, next_steps)
        result2 = build_repro_json(title, assumptions, commands, needs, next_steps)

        assert result1 == result2

    def test_key_order_preservation(self):
        """Test that key order is preserved as specified."""
        result = build_repro_json(
            "Test", ["A"], [("cmd", 1, "reason")], ["need"], ["step"]
        )

        # Check top-level key order
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

        # Check command object key order
        if result["commands"]:
            cmd_keys = list(result["commands"][0].keys())
            expected_cmd_keys = [
                "cmd",
                "score",
                "rationale",
                "matched_keywords",
                "matched_langs",
            ]
            assert cmd_keys == expected_cmd_keys

    def test_schema_versioning_fields(self):
        """Test that schema versioning fields are present with correct values."""
        from autorepro import __version__

        result = build_repro_json(
            "Test", ["A"], [("cmd", 1, "reason")], ["need"], ["step"]
        )

        # Check schema versioning fields are present and have correct values
        assert "schema_version" in result
        assert result["schema_version"] == 1
        assert isinstance(result["schema_version"], int)

        assert "tool" in result
        assert result["tool"] == "autorepro"
        assert isinstance(result["tool"], str)

        assert "tool_version" in result
        assert result["tool_version"] == __version__
        assert isinstance(result["tool_version"], str)

        # Ensure these fields are at the beginning of the JSON
        keys_list = list(result.keys())
        assert keys_list[0] == "schema_version"
        assert keys_list[1] == "tool"
        assert keys_list[2] == "tool_version"
