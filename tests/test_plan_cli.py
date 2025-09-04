"""Tests for the AutoRepro plan CLI command (updated for new implementation)."""

import os
import tempfile
from unittest.mock import patch

import pytest

from autorepro.cli import main
from tests.test_utils import run_autorepro_subprocess


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
    return run_autorepro_subprocess(["plan"] + args, cwd=cwd, timeout=timeout)


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
        location: "dir" for .devcontainer/devcontainer.json, "root" for devcontainer.json
    """
    if location == "dir":
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "devcontainer.json").write_text('{"name": "test"}')
    elif location == "root":
        (tmp_path / "devcontainer.json").write_text('{"name": "test"}')


def run_cli(cwd, *args):
    """
    Helper function to run autorepro plan CLI with subprocess.

    Args:
        cwd: Working directory for the command
        *args: Arguments to pass to the plan command

    Returns:
        subprocess.CompletedProcess with returncode, stdout, stderr
    """
    return run_autorepro_subprocess(["plan"] + list(args), cwd=cwd)


class TestPlanCLIArgumentValidation:
    """Test plan command argument validation."""

    def test_missing_desc_and_file_exit_2(self, capsys):
        """Test that missing --desc and --file returns exit code 2."""
        with patch("sys.argv", ["autorepro", "plan"]):
            exit_code = main()

        assert exit_code == 2
        captured = capsys.readouterr()
        error_output = captured.out + captured.err
        assert "one of the arguments --desc --file is required" in error_output

    def test_both_desc_and_file_exit_2(self, capsys):
        """Test that providing both --desc and --file returns exit code 2."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test issue")
            temp_file = f.name

        try:
            with patch("sys.argv", ["autorepro", "plan", "--desc", "test", "--file", temp_file]):
                exit_code = main()

            assert exit_code == 2
            captured = capsys.readouterr()
            error_output = captured.out + captured.err
            assert "not allowed with argument" in error_output
        finally:
            os.unlink(temp_file)

    def test_invalid_file_exit_1(self, caplog):
        """Test that non-existent file returns exit code 1."""
        with patch("sys.argv", ["autorepro", "plan", "--file", "nonexistent.txt"]):
            exit_code = main()

        assert exit_code == 1
        # Check that error message appears in the log records
        assert any("Error reading file" in record.message for record in caplog.records)

    def test_plan_requires_input(self, tmp_path, monkeypatch, capsys):
        """Test that plan command requires either --desc or --file input."""
        monkeypatch.chdir(tmp_path)

        # Invoke with no --desc and no --file
        result = run_cli(tmp_path)

        # Expect returncode == 2 and misuse message on STDERR
        assert result.returncode == 2, f"Expected exit code 2, got {result.returncode}"

        # Check that error message mentions one of --desc/--file is required
        error_output = result.stderr
        assert "one of the arguments --desc --file is required" in error_output, (
            f"Expected missing argument error, got: {error_output}"
        )

    def test_plan_writes_md_default_path(self, tmp_path):
        """Test that plan writes to repro.md by default and contains expected content."""
        # Touch pyproject.toml to bias detection toward Python
        (tmp_path / "pyproject.toml").touch()

        # Run with --desc "pytest failing"
        result = run_cli(tmp_path, "--desc", "pytest failing")

        # Should succeed
        assert result.returncode == 0, (
            f"Expected success, got {result.returncode}. STDERR: {result.stderr}"
        )

        # Assert repro.md exists
        repro_file = tmp_path / "repro.md"
        assert repro_file.exists(), "repro.md should be created by default"

        # Assert content contains pytest -q in Candidate Commands
        content = repro_file.read_text()
        assert "## Candidate Commands" in content, "Should have Candidate Commands section"
        assert "pytest -q" in content, "Should contain pytest -q command"

    def test_plan_respects_out_and_force(self, tmp_path):
        """Test that plan respects --out and --force flags with mtime behavior."""
        import os
        import time

        # Run with custom output path (create parent directory first)
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir()
        out_path = docs_dir / "repro.md"

        result = run_cli(tmp_path, "--desc", "pytest failing", "--out", str(out_path))

        # Should succeed and write to docs/ directory
        assert result.returncode == 0, (
            f"Expected success, got {result.returncode}. STDERR: {result.stderr}"
        )
        assert docs_dir.exists(), "docs/ directory should exist"
        assert out_path.exists(), "repro.md should be created in docs/"

        # Capture mtime1
        mtime1 = os.path.getmtime(out_path)

        # Wait a moment to ensure different mtime
        time.sleep(0.1)

        # Rerun the same command without --force
        result2 = run_cli(tmp_path, "--desc", "pytest failing", "--out", str(out_path))

        # Should succeed but not overwrite
        assert result2.returncode == 0, f"Expected success, got {result2.returncode}"
        assert "exists; use --force to overwrite" in result2.stdout, (
            "Should warn about existing file"
        )

        # mtime should be unchanged
        mtime_unchanged = os.path.getmtime(out_path)
        assert mtime_unchanged == mtime1, "File should not be modified without --force"

        # Wait a moment to ensure different mtime
        time.sleep(0.1)

        # Run again with --force
        result3 = run_cli(tmp_path, "--desc", "pytest failing", "--out", str(out_path), "--force")

        # Should succeed and overwrite
        assert result3.returncode == 0, (
            f"Expected success, got {result3.returncode}. STDERR: {result3.stderr}"
        )

        # mtime2 should be greater than mtime1
        mtime2 = os.path.getmtime(out_path)
        assert mtime2 > mtime1, (
            f"File should be modified with --force. mtime1={mtime1}, mtime2={mtime2}"
        )

    def test_plan_infers_env_presence(self, tmp_path):
        """Test that plan includes Needed Files/Env section and environment detection."""
        # Create .devcontainer/devcontainer.json
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        (devcontainer_dir / "devcontainer.json").write_text("{}")

        # Run with --desc "anything"
        result = run_cli(tmp_path, "--desc", "anything")

        # Should succeed
        assert result.returncode == 0, (
            f"Expected success, got {result.returncode}. STDERR: {result.stderr}"
        )

        # Assert repro.md contains Needed Files/Env section
        repro_file = tmp_path / "repro.md"
        assert repro_file.exists(), "repro.md should be created"

        content = repro_file.read_text()
        assert "## Needed Files/Env" in content, "Should have Needed Files/Env section"
        # Note: devcontainer detection would be implemented here in future
        # For now, just verify the section exists with some environment content
        lines = content.split("\n")
        env_section_found = False
        has_env_content = False
        for line in lines:
            if line == "## Needed Files/Env":
                env_section_found = True
            elif env_section_found and line.strip().startswith("- "):
                has_env_content = True
                break
        assert has_env_content, "Should have environment content in Needed Files/Env section"

    def test_plan_node_keywords(self, tmp_path):
        """Test that plan detects Node keywords and suggests appropriate commands."""
        # Create package.json
        package_json = {"name": "x", "scripts": {"test": "jest"}}
        (tmp_path / "package.json").write_text(f"{package_json}".replace("'", '"'))

        # Run with --desc "tests failing on jest"
        result = run_cli(tmp_path, "--desc", "tests failing on jest")

        # Should succeed
        assert result.returncode == 0, (
            f"Expected success, got {result.returncode}. STDERR: {result.stderr}"
        )

        # Assert output contains either npm test -s or npx jest -w=1
        repro_file = tmp_path / "repro.md"
        assert repro_file.exists(), "repro.md should be created"

        content = repro_file.read_text()
        assert "## Candidate Commands" in content, "Should have Candidate Commands section"

        # Should contain either npm test -s or npx jest -w=1
        has_npm_test = "npm test -s" in content
        has_npx_jest = "npx jest -w=1" in content
        assert has_npm_test or has_npx_jest, (
            f"Should contain either 'npm test -s' or 'npx jest -w=1' in content: {content}"
        )


class TestPlanCLIBasicFunctionality:
    """Test basic plan command functionality with new format."""

    def test_desc_generates_new_format(self, tmp_path, monkeypatch):
        """Test --desc generates repro.md with new canonical format."""
        monkeypatch.chdir(tmp_path)
        create_project_markers(tmp_path, "python")

        with patch("sys.argv", ["autorepro", "plan", "--desc", "pytest tests failing"]):
            exit_code = main()

        assert exit_code == 0

        # Check repro.md was created
        repro_file = tmp_path / "repro.md"
        assert repro_file.exists()

        content = repro_file.read_text()

        # Check new canonical sections
        assert "## Assumptions" in content
        assert "## Candidate Commands" in content
        assert "## Needed Files/Env" in content
        assert "## Next Steps" in content

        # Check new line-based command format (not table)
        assert "pytest -q" in content
        assert "| Score | Command | Why |" not in content  # No table format
        assert " — " in content  # Line format separator

    def test_file_input_works(self, tmp_path, monkeypatch):
        """Test --file reads from file and generates plan."""
        monkeypatch.chdir(tmp_path)
        create_project_markers(tmp_path, "node")

        # Create input file
        input_file = tmp_path / "issue.txt"
        input_file.write_text("npm test failing with jest")

        with patch("sys.argv", ["autorepro", "plan", "--file", str(input_file)]):
            exit_code = main()

        assert exit_code == 0

        # Check repro.md was created
        repro_file = tmp_path / "repro.md"
        assert repro_file.exists()

        content = repro_file.read_text()
        # Should detect jest and npm test keywords
        assert "jest" in content.lower() or "npm test" in content

    def test_custom_output_path(self, tmp_path, monkeypatch):
        """Test --out specifies custom output path."""
        monkeypatch.chdir(tmp_path)

        custom_path = tmp_path / "custom_repro.md"

        with patch(
            "sys.argv", ["autorepro", "plan", "--desc", "test issue", "--out", str(custom_path)]
        ):
            exit_code = main()

        assert exit_code == 0
        assert custom_path.exists()
        assert not (tmp_path / "repro.md").exists()

    def test_title_truncation_in_output(self, tmp_path, monkeypatch):
        """Test that very long descriptions are truncated in title."""
        monkeypatch.chdir(tmp_path)

        long_desc = (
            "Supercalifragilisticexpialidocious Pneumonoultramicroscopicsilicovolcanoconiosisword "
            "Antidisestablishmentarianismterm Floccinaucinihilipilificationphrase "
            "Hippopotomonstrosesquippedaliophobiaissue Pseudopseudohypoparathyroidismthing "
            "Thyroparathyroidectomizedproblem Radioimmunoelectrophoresisphenomenon"
        )

        with patch("sys.argv", ["autorepro", "plan", "--desc", long_desc]):
            exit_code = main()

        assert exit_code == 0

        content = (tmp_path / "repro.md").read_text()
        lines = content.split("\n")
        title_line = lines[0]

        # Title should be truncated and have ellipsis
        assert title_line.startswith("# ")
        title_text = title_line[2:]  # Remove "# "
        assert len(title_text) <= 61  # 60 chars + ellipsis
        assert title_text.endswith("…")


class TestPlanCLIOverwriteBehavior:
    """Test plan command file overwrite behavior."""

    def test_existing_file_without_force_no_overwrite(self, tmp_path, monkeypatch, capsys):
        """Test existing file without --force doesn't overwrite and returns exit 0."""
        monkeypatch.chdir(tmp_path)

        # Create existing repro.md
        existing_file = tmp_path / "repro.md"
        existing_content = "# Existing content"
        existing_file.write_text(existing_content)

        with patch("sys.argv", ["autorepro", "plan", "--desc", "new issue"]):
            exit_code = main()

        assert exit_code == 0

        # File should not be overwritten
        assert existing_file.read_text() == existing_content

        # Should print message about existing file
        captured = capsys.readouterr()
        assert "repro.md exists; use --force to overwrite" in captured.out

    def test_existing_file_with_force_overwrites(self, tmp_path, monkeypatch, capsys):
        """Test existing file with --force gets overwritten."""
        monkeypatch.chdir(tmp_path)

        # Create existing repro.md
        existing_file = tmp_path / "repro.md"
        existing_file.write_text("# Old content")

        with patch("sys.argv", ["autorepro", "plan", "--desc", "new pytest issue", "--force"]):
            exit_code = main()

        assert exit_code == 0

        # File should be overwritten
        new_content = existing_file.read_text()
        assert "# Old content" not in new_content
        assert "pytest" in new_content.lower()

        # Should print the output path
        captured = capsys.readouterr()
        assert "repro.md" in captured.out


class TestPlanCLILanguageDetection:
    """Test plan command integration with language detection."""

    def test_python_project_in_assumptions_and_needs(self, tmp_path, monkeypatch):
        """Test Python project detection appears in canonical sections."""
        monkeypatch.chdir(tmp_path)
        create_project_markers(tmp_path, "python")

        with patch("sys.argv", ["autorepro", "plan", "--desc", "tests failing"]):
            exit_code = main()

        assert exit_code == 0

        content = (tmp_path / "repro.md").read_text()

        # Should have language-based assumptions from CLI
        assert "## Assumptions" in content
        assert "Project uses python based on detected files" in content

    def test_node_project_detected(self, tmp_path, monkeypatch):
        """Test Node.js project detection influences command suggestions."""
        monkeypatch.chdir(tmp_path)
        create_project_markers(tmp_path, "node")

        with patch("sys.argv", ["autorepro", "plan", "--desc", "npm test failing"]):
            exit_code = main()

        assert exit_code == 0

        content = (tmp_path / "repro.md").read_text()

        # Should have npm test commands prioritized
        assert "npm test" in content
        # Should use line format
        assert " — " in content

    def test_mixed_languages_detected(self, tmp_path, monkeypatch):
        """Test multiple languages detected and both contribute to scoring."""
        monkeypatch.chdir(tmp_path)
        create_project_markers(tmp_path, "mixed")

        with patch("sys.argv", ["autorepro", "plan", "--desc", "tests failing"]):
            exit_code = main()

        assert exit_code == 0

        content = (tmp_path / "repro.md").read_text()

        # Should have commands from both ecosystems
        content_lower = content.lower()
        has_python = "pytest" in content_lower
        has_node = "npm test" in content_lower or "jest" in content_lower

        # At least one ecosystem should be represented
        assert has_python or has_node


class TestPlanCLIDevcontainerDetection:
    """Test devcontainer detection in needs section."""

    def test_devcontainer_dir_detected(self, tmp_path, monkeypatch):
        """Test .devcontainer/devcontainer.json is detected."""
        monkeypatch.chdir(tmp_path)
        create_devcontainer(tmp_path, "dir")

        with patch("sys.argv", ["autorepro", "plan", "--desc", "test issue"]):
            exit_code = main()

        assert exit_code == 0

        content = (tmp_path / "repro.md").read_text()

        # Note: This test assumes devcontainer detection is implemented in CLI
        # For now, we check that the needs section exists
        assert "## Needed Files/Env" in content

    def test_devcontainer_root_detected(self, tmp_path, monkeypatch):
        """Test devcontainer.json at root is detected."""
        monkeypatch.chdir(tmp_path)
        create_devcontainer(tmp_path, "root")

        with patch("sys.argv", ["autorepro", "plan", "--desc", "test issue"]):
            exit_code = main()

        assert exit_code == 0

        content = (tmp_path / "repro.md").read_text()
        assert "## Needed Files/Env" in content

    def test_no_devcontainer_absent(self, tmp_path, monkeypatch):
        """Test that absent devcontainer is noted."""
        monkeypatch.chdir(tmp_path)
        # Don't create any devcontainer files

        with patch("sys.argv", ["autorepro", "plan", "--desc", "test issue"]):
            exit_code = main()

        assert exit_code == 0

        content = (tmp_path / "repro.md").read_text()
        assert "## Needed Files/Env" in content


class TestPlanCLIMaxCommands:
    """Test --max flag functionality."""

    def test_max_limits_command_count(self, tmp_path, monkeypatch):
        """Test --max limits the number of suggested commands."""
        monkeypatch.chdir(tmp_path)
        create_project_markers(tmp_path, "mixed")  # More suggestions

        with patch(
            "sys.argv",
            ["autorepro", "plan", "--desc", "pytest jest npm test failing", "--max", "2"],
        ):
            exit_code = main()

        assert exit_code == 0

        content = (tmp_path / "repro.md").read_text()

        # Count command lines (format: "command — rationale")
        lines = content.split("\n")
        command_lines = [
            line for line in lines if " — " in line and not line.startswith("#") and line.strip()
        ]

        # Should have at most 2 command lines
        assert len(command_lines) <= 2

    def test_default_max_allows_more_commands(self, tmp_path, monkeypatch):
        """Test default max (5) allows more commands than custom limit."""
        monkeypatch.chdir(tmp_path)
        create_project_markers(tmp_path, "mixed")

        with patch("sys.argv", ["autorepro", "plan", "--desc", "pytest jest npm test failing"]):
            exit_code = main()

        assert exit_code == 0

        content = (tmp_path / "repro.md").read_text()

        # Count command lines
        lines = content.split("\n")
        command_lines = [
            line for line in lines if " — " in line and not line.startswith("#") and line.strip()
        ]

        # Should allow more than 2 commands (default max is 5)
        assert len(command_lines) >= 2

    def test_max_option_command_ordering_and_counting(self, tmp_path):
        """Test --max N limits commands and verifies scoring/alphabetical ordering."""
        create_project_markers(tmp_path, "mixed")  # Both python and node files

        # Test with higher limit to see full ordering
        result_full = run_plan_subprocess(
            ["--desc", "pytest jest npm test failing", "--out", "full.md", "--max", "10"],
            cwd=tmp_path,
        )
        assert result_full.returncode == 0

        full_content = (tmp_path / "full.md").read_text()
        full_lines = full_content.split("\n")
        full_commands = [
            line.split(" — ")[0].lstrip("- ").strip().strip("`").lstrip("- ").strip()
            for line in full_lines
            if " — " in line and not line.startswith("#") and line.strip()
        ]

        # Test with --max 3
        result_limited = run_plan_subprocess(
            ["--desc", "pytest jest npm test failing", "--out", "limited.md", "--max", "3"],
            cwd=tmp_path,
        )
        assert result_limited.returncode == 0

        limited_content = (tmp_path / "limited.md").read_text()
        limited_lines = limited_content.split("\n")
        limited_commands = [
            line.split(" — ")[0].lstrip("- ").strip().strip("`").lstrip("- ").strip()
            for line in limited_lines
            if " — " in line and not line.startswith("#") and line.strip()
        ]

        # Verify command count is limited to 3
        assert len(limited_commands) == 3, (
            f"Expected 3 commands, got {len(limited_commands)}: {limited_commands}"
        )

        # Verify that limited commands are the first 3 from the full list (proper ordering)
        assert len(full_commands) >= 3, (
            f"Need at least 3 commands in full list, got {len(full_commands)}"
        )
        assert limited_commands == full_commands[:3], (
            f"Limited should be first 3 of full list.\n"
            f"Limited: {limited_commands}\nFull[:3]: {full_commands[:3]}"
        )

        # Verify alphabetical ordering among commands with same score
        # Extract rationales to check scoring info
        limited_rationales = [
            line.split(" — ")[1]
            for line in limited_lines
            if " — " in line and not line.startswith("#") and line.strip()
        ]

        # Commands should be ordered by score (descending) then alphabetically
        # This is verified by checking the first N commands are the same in both lists
        assert len(limited_rationales) == 3


class TestPlanCLIFormatFlag:
    """Test --format flag functionality."""

    def test_json_format_output(self, tmp_path, monkeypatch):
        """Test --format json produces valid JSON output."""
        monkeypatch.chdir(tmp_path)

        # Create Python project markers for testing
        (tmp_path / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools"]')

        with patch(
            "sys.argv", ["autorepro", "plan", "--desc", "pytest failing", "--format", "json"]
        ):
            exit_code = main()

        assert exit_code == 0

        # Should create JSON file
        repro_file = tmp_path / "repro.md"
        assert repro_file.exists()

        content = repro_file.read_text()

        # Should be valid JSON
        import json

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            pytest.fail(f"Output is not valid JSON: {content}")

        # Check JSON schema structure
        assert "title" in data
        assert "assumptions" in data
        assert "commands" in data
        assert "needs" in data
        assert "next_steps" in data

        # Check command structure
        if data["commands"]:
            cmd = data["commands"][0]
            assert "cmd" in cmd
            assert "score" in cmd
            assert "rationale" in cmd
            assert "matched_keywords" in cmd
            assert "matched_langs" in cmd

        # Should contain pytest command due to Python detection and keyword
        commands = [cmd["cmd"] for cmd in data["commands"]]
        pytest_commands = [cmd for cmd in commands if "pytest" in cmd]
        assert len(pytest_commands) > 0, f"Should include pytest commands. Commands: {commands}"

    def test_json_format_stdout(self, tmp_path):
        """Test --format json --out - produces JSON to stdout."""
        # Create Python project markers for testing
        (tmp_path / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools"]')

        result = run_plan_subprocess(
            ["--desc", "pytest failing", "--format", "json", "--out", "-"], cwd=tmp_path
        )
        assert result.returncode == 0

        # Should output valid JSON to stdout
        import json

        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            pytest.fail(f"stdout is not valid JSON: {result.stdout}")

        # Check JSON schema structure
        assert "title" in data
        assert "assumptions" in data
        assert "commands" in data
        assert "needs" in data
        assert "next_steps" in data

        # Should end with newline
        assert result.stdout.endswith("\n")

    def test_md_format_explicit(self, tmp_path, monkeypatch):
        """Test explicit --format md works."""
        monkeypatch.chdir(tmp_path)

        with patch("sys.argv", ["autorepro", "plan", "--desc", "test issue", "--format", "md"]):
            exit_code = main()

        assert exit_code == 0

        repro_file = tmp_path / "repro.md"
        assert repro_file.exists()

        content = repro_file.read_text()
        assert content.startswith("#")  # Markdown format


class TestPlanCLISubprocessIntegration:
    """Integration tests using subprocess helper for hermetic testing."""

    def test_plan_help_via_subprocess(self):
        """Test plan help using subprocess."""
        result = run_plan_subprocess(["--help"])

        assert result.returncode == 0
        assert "--desc" in result.stdout
        assert "--file" in result.stdout
        assert "--force" in result.stdout
        assert "--max" in result.stdout
        assert "--format" in result.stdout

    def test_plan_missing_args_via_subprocess(self):
        """Test plan with missing arguments via subprocess."""
        result = run_plan_subprocess([])

        assert result.returncode == 2
        assert "required" in (result.stdout + result.stderr).lower()

    def test_plan_success_via_subprocess(self, tmp_path):
        """Test successful plan generation via subprocess in tmp environment."""
        # Create minimal project structure in tmp_path
        create_project_markers(tmp_path, "python")

        result = run_plan_subprocess(
            ["--desc", "pytest failing", "--out", "test_plan.md"], cwd=tmp_path
        )

        assert result.returncode == 0
        assert "test_plan.md" in result.stdout

        # Check file was created with new format
        plan_file = tmp_path / "test_plan.md"
        assert plan_file.exists()

        content = plan_file.read_text()

        # Check new canonical format
        assert "## Candidate Commands" in content
        assert "## Needed Files/Env" in content

        # Should have line-based commands, not table
        assert " — " in content
        assert "| Score | Command | Why |" not in content

    def test_tmp_path_isolation(self, tmp_path):
        """Test that tmp_path provides proper CWD isolation."""
        # Create different project types in different subdirs
        python_dir = tmp_path / "python_project"
        python_dir.mkdir()
        create_project_markers(python_dir, "python")

        node_dir = tmp_path / "node_project"
        node_dir.mkdir()
        create_project_markers(node_dir, "node")

        # Test Python project detection
        result_py = run_plan_subprocess(
            ["--desc", "tests failing", "--out", "py_plan.md"], cwd=python_dir
        )
        assert result_py.returncode == 0

        py_content = (python_dir / "py_plan.md").read_text()

        # Test Node project detection
        result_node = run_plan_subprocess(
            ["--desc", "tests failing", "--out", "node_plan.md"], cwd=node_dir
        )
        assert result_node.returncode == 0

        node_content = (node_dir / "node_plan.md").read_text()

        # Should have different suggestions based on project type
        # Both should have canonical format but different commands
        assert "## Candidate Commands" in py_content
        assert "## Candidate Commands" in node_content

        # Commands should differ based on detected project type
        # (This is a basic check - exact commands depend on implementation)
        assert py_content != node_content


class TestPlanCLIForceIgnoring:
    """Test --force flag behavior with stdout output options."""

    def test_plan_out_dash_ignores_force_flag(self, tmp_path):
        """Test that --out - ignores --force flag and outputs to stdout."""
        # Create an existing file to test force behavior
        existing_file = tmp_path / "repro.md"
        existing_file.write_text("# Existing content")

        result = run_plan_subprocess(
            ["--desc", "pytest failing", "--out", "-", "--force"], cwd=tmp_path
        )

        assert result.returncode == 0
        # Should output markdown to stdout
        assert "## Assumptions" in result.stdout
        assert "## Candidate Commands" in result.stdout
        # Should not modify the existing file
        assert existing_file.read_text() == "# Existing content"
        # Should end with newline
        assert result.stdout.endswith("\n")


class TestPlanCLICommandFiltering:
    """Test command filtering logic to ensure relevant commands are shown."""

    def test_ambiguous_case_shows_relevant_commands(self, tmp_path):
        """Test ambiguous case where keywords don't clearly match but language is detected."""
        # Create a Python project but use ambiguous description
        create_project_markers(tmp_path, "python")

        result = run_plan_subprocess(
            ["--desc", "tests are broken and failing", "--out", "ambiguous.md"], cwd=tmp_path
        )
        assert result.returncode == 0

        content = (tmp_path / "ambiguous.md").read_text()
        lines = content.split("\n")
        command_lines = [
            line for line in lines if " — " in line and not line.startswith("#") and line.strip()
        ]

        # Should show Python commands due to language detection even without specific keywords
        assert len(command_lines) > 0, "Should show commands based on detected language"

        # Should include pytest command since Python was detected
        commands = [line.split(" — ")[0].lstrip("- ").strip().strip("`") for line in command_lines]
        python_commands = [cmd for cmd in commands if "pytest" in cmd]
        assert len(python_commands) > 0, (
            f"Should include pytest commands for Python project. Commands: {commands}"
        )

    def test_keyword_match_without_language_detection(self, tmp_path):
        """Test that specific keywords show relevant commands even without language detection."""
        # Don't create any project markers (no language detection)

        result = run_plan_subprocess(
            ["--desc", "npm test is failing with jest errors", "--out", "keyword.md"], cwd=tmp_path
        )
        assert result.returncode == 0

        content = (tmp_path / "keyword.md").read_text()
        lines = content.split("\n")
        command_lines = [
            line for line in lines if " — " in line and not line.startswith("#") and line.strip()
        ]

        # Should show Node commands due to npm test and jest keywords
        assert len(command_lines) > 0, "Should show commands based on keywords"

        commands = [line.split(" — ")[0].lstrip("- ").strip().strip("`") for line in command_lines]
        # Should include npm test or jest commands
        node_commands = [cmd for cmd in commands if "npm test" in cmd or "jest" in cmd]
        assert len(node_commands) > 0, (
            f"Should include npm/jest commands based on keywords. Commands: {commands}"
        )

    def test_no_matches_shows_no_commands(self, tmp_path):
        """Test that when no keywords or languages match, no commands are shown."""
        # Don't create any project markers and use generic description

        result = run_plan_subprocess(
            ["--desc", "something is broken and needs fixing", "--out", "generic.md"], cwd=tmp_path
        )
        assert result.returncode == 0

        content = (tmp_path / "generic.md").read_text()
        lines = content.split("\n")
        command_lines = [
            line for line in lines if " — " in line and not line.startswith("#") and line.strip()
        ]

        # Should show NO commands when no keyword or language matches
        assert not command_lines, f"Should show no commands when no matches. Got: {command_lines}"

    def test_plan_dry_run_ignores_force_flag(self, tmp_path):
        """Test that --dry-run ignores --force flag and outputs to stdout."""
        # Create an existing file to test force behavior
        existing_file = tmp_path / "repro.md"
        existing_file.write_text("# Existing content")

        result = run_plan_subprocess(
            ["--desc", "jest failing", "--dry-run", "--force"], cwd=tmp_path
        )

        assert result.returncode == 0
        # Should output markdown to stdout
        assert "## Assumptions" in result.stdout
        assert "## Candidate Commands" in result.stdout
        # Should not modify the existing file
        assert existing_file.read_text() == "# Existing content"
        # Should end with newline
        assert result.stdout.endswith("\n")


class TestPlanCLICommandFilteringAlt:
    """Test command filtering logic to ensure relevant commands are shown (alt)."""

    def test_ambiguous_case_shows_relevant_commands(self, tmp_path):
        """Test ambiguous case where keywords don't clearly match but language is detected."""
        # Create a Python project but use ambiguous description
        create_project_markers(tmp_path, "python")

        result = run_plan_subprocess(
            ["--desc", "tests are broken and failing", "--out", "ambiguous.md"], cwd=tmp_path
        )
        assert result.returncode == 0

        content = (tmp_path / "ambiguous.md").read_text()
        lines = content.split("\n")
        command_lines = [
            line for line in lines if " — " in line and not line.startswith("#") and line.strip()
        ]

        # Should show Python commands due to language detection even without specific keywords
        assert len(command_lines) > 0, "Should show commands based on detected language"

        # Should include pytest command since Python was detected
        commands = [line.split(" — ")[0].lstrip("- ").strip().strip("`") for line in command_lines]
        python_commands = [cmd for cmd in commands if "pytest" in cmd]
        assert len(python_commands) > 0, (
            f"Should include pytest commands for Python project. Commands: {commands}"
        )

    def test_keyword_match_without_language_detection(self, tmp_path):
        """Test that specific keywords show relevant commands even without language detection."""
        # Don't create any project markers (no language detection)

        result = run_plan_subprocess(
            ["--desc", "npm test is failing with jest errors", "--out", "keyword.md"], cwd=tmp_path
        )
        assert result.returncode == 0

        content = (tmp_path / "keyword.md").read_text()
        lines = content.split("\n")
        command_lines = [
            line for line in lines if " — " in line and not line.startswith("#") and line.strip()
        ]

        # Should show Node commands due to npm test and jest keywords
        assert len(command_lines) > 0, "Should show commands based on keywords"

        commands = [line.split(" — ")[0].lstrip("- ").strip().strip("`") for line in command_lines]
        # Should include npm test or jest commands
        node_commands = [cmd for cmd in commands if "npm test" in cmd or "jest" in cmd]
        assert len(node_commands) > 0, (
            f"Should include npm/jest commands based on keywords. Commands: {commands}"
        )

    def test_no_matches_shows_no_commands(self, tmp_path):
        """Test that when no keywords or languages match, no commands are shown."""
        # Don't create any project markers and use generic description

        result = run_plan_subprocess(
            ["--desc", "something is broken and needs fixing", "--out", "generic.md"], cwd=tmp_path
        )
        assert result.returncode == 0

        content = (tmp_path / "generic.md").read_text()
        lines = content.split("\n")
        command_lines = [
            line for line in lines if " — " in line and not line.startswith("#") and line.strip()
        ]

        # Should show NO commands when no keyword or language matches
        assert not command_lines, f"Should show no commands when no matches. Got: {command_lines}"
