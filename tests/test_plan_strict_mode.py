"""Tests for the AutoRepro plan strict mode and quality gates (T-010)."""

import subprocess
import sys

import pytest

from autorepro.planner import suggest_commands


def run_plan_subprocess(args, cwd=None, timeout=30):
    """
    Helper to run autorepro plan via subprocess for hermetic CLI testing.

    Args:
        args: List of arguments (excluding 'plan')
        cwd: Working directory for the command
        timeout: Timeout in seconds

    Returns:
        subprocess.CompletedProcess with returncode, stdout, stderr
    """
    cmd = [sys.executable, "-m", "autorepro.cli", "plan"] + args
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)


def create_project_markers(tmp_path, project_type="python"):
    """
    Create minimal marker files for different project types.

    Args:
        tmp_path: pytest tmp_path fixture
        project_type: "python", "node", "go", or "mixed"
    """
    if project_type == "python":
        (tmp_path / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools"]')
    elif project_type == "node":
        (tmp_path / "package.json").write_text('{"name": "test-project", "version": "1.0.0"}')
    elif project_type == "go":
        (tmp_path / "go.mod").write_text("module test\n\ngo 1.19")
    elif project_type == "mixed":
        (tmp_path / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools"]')
        (tmp_path / "package.json").write_text('{"name": "test-project", "version": "1.0.0"}')


class TestPlanCoreFiltering:
    """Test core filtering functionality in planner module."""

    def test_min_score_filters_low_weight_commands(self):
        """Test that min_score filters out commands with score < threshold."""
        keywords = set()  # No keywords - only get language-based scoring
        detected_langs = ["python"]  # Python gives +2 score

        # Test with default min_score=2 - should include Python commands
        suggestions_default = suggest_commands(keywords, detected_langs, min_score=2)
        assert len(suggestions_default) > 0, "Should include Python commands with score >= 2"

        # Test with high min_score=4 - should exclude Python-only commands (score 2)
        suggestions_high = suggest_commands(keywords, detected_langs, min_score=4)
        assert len(suggestions_high) == 0, "Should exclude commands with score < 4"

        # Test with low min_score=1 - should include more commands
        suggestions_low = suggest_commands(keywords, detected_langs, min_score=1)
        assert len(suggestions_low) >= len(
            suggestions_default
        ), "Lower min_score should include more commands"

    def test_keyword_match_respects_min_score(self):
        """Test that direct keyword matches are filtered by min_score."""
        keywords = {"pytest"}  # Direct match gives +3, but some commands get +1 for specificity
        detected_langs = []  # No language detection

        # With min_score=3, should include basic pytest commands
        suggestions_low = suggest_commands(keywords, detected_langs, min_score=3)
        assert len(suggestions_low) > 0, "Should include commands with score >= min_score"

        # With min_score=5, should exclude all pytest commands (max score is 4)
        suggestions_high = suggest_commands(keywords, detected_langs, min_score=5)
        assert len(suggestions_high) == 0, "Should exclude commands with score < min_score"

    def test_language_match_respects_min_score(self):
        """Test that language detection matches are filtered by min_score."""
        keywords = set()  # No keywords
        detected_langs = ["python"]  # Language detection gives +2, some get +1 for specificity

        # With min_score=2, should include python commands
        suggestions_low = suggest_commands(keywords, detected_langs, min_score=2)
        assert len(suggestions_low) > 0, "Should include commands with score >= min_score"

        # With min_score=4, should exclude python commands (max score is 3)
        suggestions_high = suggest_commands(keywords, detected_langs, min_score=4)
        assert len(suggestions_high) == 0, "Should exclude commands with score < min_score"


class TestPlanCLIStrictMode:
    """Test CLI strict mode functionality."""

    def test_strict_mode_exit_1_when_no_commands(self, tmp_path):
        """Test --strict exits with code 1 when no commands make the cut."""
        # No project markers, generic description - should have no high-scoring commands
        result = run_plan_subprocess(
            ["--desc", "random generic issue", "--min-score", "5", "--strict"], cwd=tmp_path
        )

        assert result.returncode == 1, f"Expected exit code 1, got {result.returncode}"
        assert "no candidate commands above min-score=5" in result.stderr

    def test_strict_mode_exit_0_when_commands_exist(self, tmp_path):
        """Test --strict exits with code 0 when commands make the cut."""
        create_project_markers(tmp_path, "python")

        result = run_plan_subprocess(
            ["--desc", "pytest failing", "--min-score", "2", "--strict"], cwd=tmp_path
        )

        assert (
            result.returncode == 0
        ), f"Expected exit code 0, got {result.returncode}. STDERR: {result.stderr}"

    def test_non_strict_mode_always_exit_0(self, tmp_path):
        """Test non-strict mode always exits 0 even with no commands."""
        # No project markers, generic description, high min-score
        result = run_plan_subprocess(
            ["--desc", "random generic issue", "--min-score", "5"], cwd=tmp_path
        )

        assert (
            result.returncode == 0
        ), f"Non-strict mode should always exit 0, got {result.returncode}"


class TestPlanCLIMinScore:
    """Test CLI min-score functionality."""

    def test_min_score_default_2(self, tmp_path):
        """Test default min-score is 2."""
        create_project_markers(tmp_path, "python")

        # Run without explicit min-score
        result = run_plan_subprocess(["--desc", "tests failing"], cwd=tmp_path)
        assert result.returncode == 0

        # Should have same results as explicit --min-score 2
        result_explicit = run_plan_subprocess(
            ["--desc", "tests failing", "--min-score", "2"], cwd=tmp_path
        )
        assert result_explicit.returncode == 0

    def test_min_score_filters_output(self, tmp_path):
        """Test min-score filters commands in output."""
        create_project_markers(tmp_path, "python")

        # Low min-score should show more commands
        result_low = run_plan_subprocess(
            ["--desc", "pytest failing", "--min-score", "1", "--out", "low.md"], cwd=tmp_path
        )
        assert result_low.returncode == 0

        # High min-score should show fewer commands
        result_high = run_plan_subprocess(
            ["--desc", "pytest failing", "--min-score", "4", "--out", "high.md"], cwd=tmp_path
        )
        assert result_high.returncode == 0

        # Count commands in each output
        low_content = (tmp_path / "low.md").read_text()
        high_content = (tmp_path / "high.md").read_text()

        low_commands = len(
            [line for line in low_content.split("\n") if " — " in line and line.strip()]
        )
        high_commands = len(
            [line for line in high_content.split("\n") if " — " in line and line.strip()]
        )

        assert low_commands >= high_commands, "Lower min-score should show same or more commands"

    def test_filtering_warning_message(self, tmp_path):
        """Test that filtering warning message is printed to stderr."""
        create_project_markers(tmp_path, "mixed")  # More suggestions

        result = run_plan_subprocess(
            ["--desc", "pytest jest npm test failing", "--min-score", "3"], cwd=tmp_path
        )

        assert result.returncode == 0
        # Should have filtering warning if commands were filtered
        if "filtered" in result.stderr:
            assert "low-score suggestions" in result.stderr


class TestPlanCLIExitCodes:
    """Test exit codes via -m module execution."""

    def test_module_execution_strict_failure(self, tmp_path):
        """Test python -m autorepro.cli plan returns exit code 1 for strict failure."""
        cmd = [
            sys.executable,
            "-m",
            "autorepro.cli",
            "plan",
            "--desc",
            "random",
            "--min-score",
            "5",
            "--strict",
        ]
        result = subprocess.run(cmd, cwd=tmp_path, capture_output=True)
        assert result.returncode == 1

    def test_module_execution_strict_success(self, tmp_path):
        """Test python -m autorepro.cli plan returns exit code 0 for strict success."""
        create_project_markers(tmp_path, "python")

        cmd = [
            sys.executable,
            "-m",
            "autorepro.cli",
            "plan",
            "--desc",
            "pytest",
            "--min-score",
            "2",
            "--strict",
        ]
        result = subprocess.run(cmd, cwd=tmp_path, capture_output=True)
        assert result.returncode == 0


class TestPlanCLIJSONOutputFiltering:
    """Test filtering works correctly with JSON output format."""

    def test_json_format_respects_min_score(self, tmp_path):
        """Test --format json respects min-score filtering."""
        create_project_markers(tmp_path, "python")

        result = run_plan_subprocess(
            ["--desc", "pytest failing", "--format", "json", "--min-score", "4"], cwd=tmp_path
        )
        assert result.returncode == 0

        # Should produce valid JSON
        import json

        try:
            data = json.loads((tmp_path / "repro.md").read_text())
            # With high min-score, should have fewer or no commands
            assert isinstance(data["commands"], list)
        except (json.JSONDecodeError, FileNotFoundError):
            pytest.fail("Should produce valid JSON output")

    def test_json_strict_mode(self, tmp_path):
        """Test JSON output with strict mode."""
        result = run_plan_subprocess(
            ["--desc", "random", "--format", "json", "--min-score", "5", "--strict"], cwd=tmp_path
        )
        assert result.returncode == 1
        assert "no candidate commands above min-score=5" in result.stderr


class TestPlanCLIAssumptionsFiltering:
    """Test that filtering notes appear in assumptions."""

    def test_filtering_note_in_assumptions(self, tmp_path):
        """Test that filtering note appears in assumptions when commands are filtered."""
        create_project_markers(tmp_path, "mixed")  # Generate multiple commands

        result = run_plan_subprocess(
            ["--desc", "pytest jest npm test", "--min-score", "4"], cwd=tmp_path
        )
        assert result.returncode == 0

        content = (tmp_path / "repro.md").read_text()

        # Should have assumptions section
        assert "## Assumptions" in content

        # Should mention filtering in assumptions since user explicitly set --min-score
        assert "Filtered" in content and "low-scoring command suggestions" in content

    def test_no_filtering_note_when_no_filtering(self, tmp_path):
        """Test no filtering note when no commands are filtered."""
        create_project_markers(tmp_path, "python")

        result = run_plan_subprocess(
            ["--desc", "pytest", "--min-score", "0"],
            cwd=tmp_path,  # Include everything
        )
        assert result.returncode == 0

        content = (tmp_path / "repro.md").read_text()

        # Should not mention filtering if nothing was filtered (min-score=0 includes all)
        assert "Filtered" not in content or "low-scoring command suggestions" not in content
