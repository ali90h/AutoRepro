"""Tests for the AutoRepro plan CLI command JSON format functionality."""

import json
import subprocess
import sys


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
    cmd = [sys.executable, "-m", "autorepro", "plan"] + args
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


def create_devcontainer(tmp_path, location="dir"):
    """
    Create devcontainer files for testing devcontainer detection.

    Args:
        tmp_path: pytest tmp_path fixture
        location: "dir" for .devcontainer/devcontainer.json or "root" for devcontainer.json
    """
    if location == "dir":
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "devcontainer.json").write_text('{"name": "test-dev"}')
    elif location == "root":
        (tmp_path / "devcontainer.json").write_text('{"name": "test-dev"}')


class TestPlanJSONFileOutput:
    """Test JSON format file output with various CLI options."""

    def test_json_file_output_basic(self, tmp_path):
        """Test --format json creates valid JSON file."""
        create_project_markers(tmp_path, "python")
        output_file = tmp_path / "repro.json"

        result = run_plan_subprocess(
            ["--desc", "pytest failing", "--format", "json", "--out", str(output_file)],
            cwd=tmp_path,
        )

        assert result.returncode == 0
        assert f"Wrote repro to {output_file}" in result.stdout

        # Verify file exists and contains valid JSON
        assert output_file.exists()
        content = output_file.read_text()

        # Must end with newline
        assert content.endswith("\n")

        # Must be valid JSON
        data = json.loads(content)
        assert isinstance(data, dict)

        # Must have required keys
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
        assert list(data.keys()) == expected_keys

    def test_json_file_output_with_force(self, tmp_path):
        """Test --format json with --force overwrites existing file."""
        create_project_markers(tmp_path, "python")
        output_file = tmp_path / "repro.json"

        # Create existing file
        output_file.write_text('{"old": "content"}\n')

        result = run_plan_subprocess(
            [
                "--desc",
                "jest failing",
                "--format",
                "json",
                "--out",
                str(output_file),
                "--force",
            ],
            cwd=tmp_path,
        )

        assert result.returncode == 0
        assert f"Wrote repro to {output_file}" in result.stdout

        # Verify file was overwritten with new content
        content = output_file.read_text()
        data = json.loads(content)
        assert data["title"] == "Jest Failing"
        assert content.endswith("\n")

    def test_json_file_exists_no_force(self, tmp_path):
        """Test --format json respects existing file without --force."""
        create_project_markers(tmp_path, "python")
        output_file = tmp_path / "repro.json"

        # Create existing file
        original_content = '{"old": "content"}\n'
        output_file.write_text(original_content)

        result = run_plan_subprocess(
            ["--desc", "pytest failing", "--format", "json", "--out", str(output_file)],
            cwd=tmp_path,
        )

        assert result.returncode == 0
        assert f"{output_file} exists; use --force to overwrite" in result.stdout

        # Verify file was not modified
        assert output_file.read_text() == original_content

    def test_json_max_commands_limit(self, tmp_path):
        """Test --max flag limits commands in JSON output."""
        create_project_markers(tmp_path, "python")
        output_file = tmp_path / "repro.json"

        result = run_plan_subprocess(
            [
                "--desc",
                "pytest failing",
                "--format",
                "json",
                "--out",
                str(output_file),
                "--max",
                "2",
            ],
            cwd=tmp_path,
        )

        assert result.returncode == 0

        content = output_file.read_text()
        data = json.loads(content)

        # Should have at most 2 commands
        assert len(data["commands"]) <= 2


class TestPlanJSONStdoutOutput:
    """Test JSON format stdout output with --out - and --dry-run."""

    def test_json_stdout_output(self, tmp_path):
        """Test --format json --out - prints valid JSON to stdout."""
        create_project_markers(tmp_path, "python")

        result = run_plan_subprocess(
            ["--desc", "pytest failing", "--format", "json", "--out", "-"], cwd=tmp_path
        )

        assert result.returncode == 0

        # Should output valid JSON to stdout
        assert result.stdout.endswith("\n")
        data = json.loads(result.stdout)
        assert isinstance(data, dict)

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
        assert list(data.keys()) == expected_keys
        assert data["title"] == "Pytest Failing"

    def test_json_dry_run_output(self, tmp_path):
        """Test --format json --dry-run prints JSON without creating file."""
        create_project_markers(tmp_path, "python")
        output_file = tmp_path / "should_not_exist.json"

        result = run_plan_subprocess(
            [
                "--desc",
                "jest failing",
                "--format",
                "json",
                "--out",
                str(output_file),
                "--dry-run",
            ],
            cwd=tmp_path,
        )

        assert result.returncode == 0

        # Should not create file
        assert not output_file.exists()

        # Should output valid JSON to stdout
        assert result.stdout.endswith("\n")
        data = json.loads(result.stdout)
        assert data["title"] == "Jest Failing"

    def test_json_stdout_ignores_force(self, tmp_path):
        """Test --format json --out - ignores --force flag."""
        create_project_markers(tmp_path, "python")

        result = run_plan_subprocess(
            [
                "--desc",
                "pytest failing",
                "--format",
                "json",
                "--out",
                "-",
                "--force",  # Should be ignored
            ],
            cwd=tmp_path,
        )

        assert result.returncode == 0

        # Should still output JSON normally
        data = json.loads(result.stdout)
        assert data["title"] == "Pytest Failing"


class TestPlanJSONWithRepo:
    """Test JSON format with --repo option."""

    def test_json_with_absolute_repo_path(self, tmp_path):
        """Test --format json with absolute --repo path."""
        # Create repo directory with markers
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()
        create_project_markers(repo_dir, "node")

        output_file = repo_dir / "repro.json"

        result = run_plan_subprocess(
            [
                "--desc",
                "npm test failing",
                "--format",
                "json",
                "--out",
                str(output_file),
                "--repo",
                str(repo_dir),
            ],
            cwd=tmp_path,
        )  # Run from different directory

        assert result.returncode == 0
        assert f"Wrote repro to {output_file}" in result.stdout

        # Verify JSON output reflects Node.js detection
        content = output_file.read_text()
        data = json.loads(content)

        # Should detect Node.js and suggest relevant commands
        command_strings = [cmd["cmd"] for cmd in data["commands"]]
        has_npm_commands = any("npm" in cmd for cmd in command_strings)
        assert has_npm_commands

    def test_json_with_relative_repo_path(self, tmp_path, monkeypatch):
        """Test --format json with relative --repo path."""
        monkeypatch.chdir(tmp_path)

        # Create relative repo directory
        repo_dir = tmp_path / "project"
        repo_dir.mkdir()
        create_project_markers(repo_dir, "go")

        result = run_plan_subprocess(
            [
                "--desc",
                "go test failing",
                "--format",
                "json",
                "--repo",
                "project",
                "--out",
                "-",
            ],
            cwd=tmp_path,
        )

        assert result.returncode == 0

        # Should output JSON with Go language detection
        data = json.loads(result.stdout)
        command_strings = [cmd["cmd"] for cmd in data["commands"]]
        has_go_commands = any("go test" in cmd for cmd in command_strings)
        assert has_go_commands

    def test_json_repo_nonexistent_path_error(self, tmp_path):
        """Test --format json with nonexistent --repo path returns error."""
        nonexistent = tmp_path / "does_not_exist"

        result = run_plan_subprocess(
            [
                "--desc",
                "test failing",
                "--format",
                "json",
                "--repo",
                str(nonexistent),
                "--out",
                "-",
            ],
            cwd=tmp_path,
        )

        assert result.returncode == 2
        assert "does not exist or is not a directory" in result.stderr


class TestPlanJSONValidation:
    """Test JSON format validation and error handling."""

    def test_json_with_missing_args_error(self, tmp_path):
        """Test --format json with missing --desc/--file returns error."""
        result = run_plan_subprocess(["--format", "json", "--out", "test.json"], cwd=tmp_path)

        assert result.returncode == 2
        assert "one of the arguments --desc --file is required" in result.stderr

    def test_json_command_structure_validation(self, tmp_path):
        """Test that JSON commands have correct structure."""
        create_project_markers(tmp_path, "python")

        result = run_plan_subprocess(
            ["--desc", "pytest and jest failing", "--format", "json", "--out", "-"],
            cwd=tmp_path,
        )

        assert result.returncode == 0

        data = json.loads(result.stdout)

        # Verify each command has correct structure
        for cmd in data["commands"]:
            expected_cmd_keys = [
                "cmd",
                "score",
                "rationale",
                "matched_keywords",
                "matched_langs",
            ]
            assert list(cmd.keys()) == expected_cmd_keys

            assert isinstance(cmd["cmd"], str)
            assert isinstance(cmd["score"], int)
            assert isinstance(cmd["rationale"], str)
            assert isinstance(cmd["matched_keywords"], list)
            assert isinstance(cmd["matched_langs"], list)

    def test_json_needs_devcontainer_detection(self, tmp_path):
        """Test JSON needs field includes devcontainer detection."""
        create_project_markers(tmp_path, "python")
        create_devcontainer(tmp_path, "dir")  # Create .devcontainer/devcontainer.json

        result = run_plan_subprocess(
            ["--desc", "pytest failing", "--format", "json", "--out", "-"], cwd=tmp_path
        )

        assert result.returncode == 0

        data = json.loads(result.stdout)
        assert "needs" in data
        assert isinstance(data["needs"], dict)
        assert "devcontainer_present" in data["needs"]
        assert data["needs"]["devcontainer_present"] is True

    def test_json_stable_command_order(self, tmp_path):
        """Test that JSON commands are in stable order (score desc, then alphabetical)."""
        create_project_markers(tmp_path, "mixed")  # Python + Node

        result = run_plan_subprocess(
            [
                "--desc",
                "pytest and jest both failing",
                "--format",
                "json",
                "--out",
                "-",
            ],
            cwd=tmp_path,
        )

        assert result.returncode == 0

        data = json.loads(result.stdout)
        commands = data["commands"]

        # Commands should be ordered by score descending, then alphabetically
        scores = [cmd["score"] for cmd in commands]

        # Check scores are in descending order or tied
        for i in range(1, len(scores)):
            assert scores[i] <= scores[i - 1], f"Scores not in descending order: {scores}"

        # Within same score, should be alphabetical
        score_groups = {}
        for cmd in commands:
            score = cmd["score"]
            if score not in score_groups:
                score_groups[score] = []
            score_groups[score].append(cmd["cmd"])

        for score, cmds in score_groups.items():
            assert cmds == sorted(cmds), f"Commands with score {score} not alphabetical: {cmds}"
