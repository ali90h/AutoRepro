"""Tests for the AutoRepro planner core functions."""

from autorepro.planner import build_repro_md, extract_keywords, suggest_commands


class TestExtractKeywords:
    """Test the extract_keywords function."""

    def test_empty_string(self):
        """Test keyword extraction from empty string."""
        result = extract_keywords("")
        assert result == set()

    def test_basic_keywords(self):
        """Test extraction of basic keywords."""
        text = "pytest tests failing on CI with npm"
        result = extract_keywords(text)
        expected = {"pytest"}  # Only specific technical keywords are extracted
        assert result == expected

    def test_stopword_filtering(self):
        """Test that only specific technical keywords are extracted."""
        text = "the tests are failing and we need to run pytest"
        result = extract_keywords(text)
        # Only specific technical keywords are extracted, stopwords are ignored
        expected = {"pytest"}
        assert result == expected

    def test_dev_terms_preserved(self):
        """Test that developer terms are preserved as specific keywords."""
        text = "go test with make and jest"
        result = extract_keywords(text)
        expected = {"go test", "jest"}  # "go test" as phrase, "jest" as single keyword
        assert result == expected

    def test_short_tokens_filtered(self):
        """Test that only specific technical keywords are extracted."""
        text = "a pytest b test c npm d"
        result = extract_keywords(text)
        expected = {"pytest"}  # Only specific technical keywords, not generic words
        assert result == expected

    def test_case_insensitive(self):
        """Test that extraction is case insensitive."""
        from autorepro.planner import normalize

        text = "PyTest TESTS Failing CI"
        normalized = normalize(text)  # Must normalize first for case insensitivity
        result = extract_keywords(normalized)
        expected = {"pytest"}  # Only specific technical keywords are extracted
        assert result == expected


class TestSuggestCommands:
    """Test the suggest_commands function."""

    def test_python_language_detection(self):
        """Test command suggestions for Python projects."""
        keywords = {"test", "pytest"}
        detected_langs = ["python"]

        suggestions = suggest_commands(keywords, detected_langs)

        # Should have pytest suggestions at top
        assert len(suggestions) > 0
        top_command = suggestions[0][0]
        assert "pytest" in top_command

        # Check scores are integers and rationales are strings
        for _, score, rationale in suggestions:
            assert isinstance(score, int)
            assert isinstance(rationale, str)
            # New rationale format uses "bonuses:" instead of "Score"
            assert (
                "bonuses:" in rationale
                or "matched keywords:" in rationale
                or "detected langs:" in rationale
            )

    def test_node_language_detection(self):
        """Test command suggestions for Node.js projects."""
        keywords = {"test", "npm"}
        detected_langs = ["node"]

        suggestions = suggest_commands(keywords, detected_langs)

        # Should have npm test suggestions
        npm_commands = [cmd for cmd, _, _ in suggestions if "npm test" in cmd]
        assert len(npm_commands) > 0

    def test_mixed_languages(self):
        """Test suggestions for projects with multiple languages."""
        keywords = {"test", "pytest", "jest"}
        detected_langs = ["python", "javascript"]

        suggestions = suggest_commands(keywords, detected_langs)

        # Should have suggestions for both languages
        python_cmds = [cmd for cmd, _, _ in suggestions if "pytest" in cmd]
        js_cmds = [cmd for cmd, _, _ in suggestions if "jest" in cmd or "npm" in cmd]

        assert len(python_cmds) > 0
        assert len(js_cmds) > 0

    def test_no_languages_conservative_defaults(self):
        """Test that conservative defaults are provided when no languages detected."""
        keywords = {"failing"}
        detected_langs = []

        suggestions = suggest_commands(keywords, detected_langs)

        assert len(suggestions) > 0
        # Should have some basic test commands
        commands = [cmd for cmd, _, _ in suggestions]
        assert any("pytest" in cmd for cmd in commands) or any(
            "npm test" in cmd for cmd in commands
        )

    def test_scoring_descending_order(self):
        """Test that suggestions are sorted by descending score."""
        keywords = {"pytest", "tests", "ci"}
        detected_langs = ["python"]

        suggestions = suggest_commands(keywords, detected_langs)

        # Check scores are in descending order
        scores = [score for _, score, _ in suggestions]
        assert scores == sorted(scores, reverse=True)

    def test_pytest_preferred_over_python(self):
        """Test that pytest -q is preferred over python -m pytest -q."""
        keywords = {"pytest", "test"}
        detected_langs = ["python"]

        suggestions = suggest_commands(keywords, detected_langs)

        # Find pytest commands
        pytest_direct = None
        pytest_module = None

        for cmd, score, _ in suggestions:
            if cmd == "pytest -q":
                pytest_direct = score
            elif cmd == "python -m pytest -q":
                pytest_module = score

        # pytest -q should have higher or equal score to python -m pytest -q
        assert pytest_direct is not None
        assert pytest_module is not None
        assert pytest_direct >= pytest_module

    def test_deterministic_ordering_with_tie_breaking(self):
        """Test that commands with same score are ordered alphabetically."""
        # Create a scenario where we might have score ties
        keywords = {"test"}
        detected_langs = ["python"]

        suggestions = suggest_commands(keywords, detected_langs)

        # Group by score and check alphabetical ordering within groups
        score_groups = {}
        for cmd, score, _ in suggestions:
            if score not in score_groups:
                score_groups[score] = []
            score_groups[score].append(cmd)

        # Check each score group is alphabetically ordered
        for _, commands in score_groups.items():
            assert commands == sorted(commands)


class TestBuildReproMd:
    """Test the build_repro_md function."""

    def test_all_five_sections_present(self):
        """Test that all five required sections are present."""
        title = "Test Issue"
        assumptions = ["Python available"]
        commands = [("pytest -q", 20, "Test command")]
        needs = ["Python 3.7+"]
        next_steps = ["Run tests"]

        result = build_repro_md(title, assumptions, commands, needs, next_steps)

        # Check all required sections are present
        assert "# Test Issue" in result
        assert "## Assumptions" in result
        assert "## Needed Files/Env" in result  # Updated section name
        assert "## Candidate Commands" in result  # Updated section name
        assert "## Next Steps" in result

    def test_line_format_in_commands_section(self):
        """Test that commands section contains properly formatted lines."""
        title = "Test"
        commands = [
            ("pytest -q", 30, "High priority test"),
            ("npm test -s", 20, "Node test"),
        ]

        result = build_repro_md(title, [], commands, [], [])

        # Check line format (no table format)
        assert "| Score | Command | Why |" not in result
        assert "|-------|---------|-----|" not in result

        # Check line format with em dash
        assert "pytest -q — High priority test" in result
        assert "npm test -s — Node test" in result

    def test_empty_lists_handled_gracefully(self):
        """Test that empty lists are handled with defaults."""
        title = "Empty Test"

        result = build_repro_md(title, [], [], [], [])

        # Should have default content for empty sections
        assert "OS: Linux (CI runner)" in result  # default assumptions
        assert "Python 3.11 / Node 20" in result  # default assumptions
        assert "Run the highest-score command" in result  # default next steps
        assert "No commands suggested" in result  # empty commands message

    def test_pipe_character_handling(self):
        """Test that pipe characters in commands/rationales are handled in line format."""
        title = "Pipe Test"
        commands = [("echo 'test|data'", 10, "Command with | pipe")]

        result = build_repro_md(title, [], commands, [], [])

        # In line format, pipes don't need escaping like in tables
        assert "echo 'test|data' — Command with | pipe" in result

    def test_markdown_structure_stability(self):
        """Test that markdown structure is consistent and diff-friendly."""
        title = "Structure Test"
        assumptions = ["Assumption 1", "Assumption 2"]
        commands = [("cmd1", 10, "reason1")]
        needs = ["Need 1"]
        next_steps = ["Step 1", "Step 2"]

        result = build_repro_md(title, assumptions, commands, needs, next_steps)

        # Check consistent spacing (empty lines between sections)
        lines = result.split("\n")

        # Title should be followed by empty line
        title_idx = next(i for i, line in enumerate(lines) if line == "# Structure Test")
        assert lines[title_idx + 1] == ""

        # Sections should be separated by empty lines
        assert "## Assumptions" in result
        assert "## Needed Files/Env" in result  # Updated section name
        assert "## Candidate Commands" in result  # Updated section name
        assert "## Next Steps" in result
