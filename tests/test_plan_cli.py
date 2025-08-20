"""Tests for the AutoRepro plan CLI command."""

import os
import subprocess
import sys
import tempfile
from unittest.mock import patch

from autorepro.cli import main


class TestPlanCLIArguments:
    """Test plan command argument handling."""

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

    def test_invalid_file_exit_1(self, capsys):
        """Test that non-existent file returns exit code 1."""
        with patch("sys.argv", ["autorepro", "plan", "--file", "nonexistent.txt"]):
            exit_code = main()

        assert exit_code == 1
        captured = capsys.readouterr()
        error_output = captured.out + captured.err
        assert "Error reading file" in error_output


class TestPlanCLIBasicFunctionality:
    """Test basic plan command functionality."""

    def test_desc_writes_repro_md_with_pytest(self, tmp_path, monkeypatch):
        """Test --desc writes repro.md containing pytest -q."""
        monkeypatch.chdir(tmp_path)

        # Create a python project indicator
        (tmp_path / "pyproject.toml").write_text("[build-system]")

        with patch("sys.argv", ["autorepro", "plan", "--desc", "pytest tests failing"]):
            exit_code = main()

        assert exit_code == 0

        # Check repro.md was created
        repro_file = tmp_path / "repro.md"
        assert repro_file.exists()

        content = repro_file.read_text()
        assert "pytest -q" in content
        assert "| Score | Command | Why |" in content

    def test_file_input_works(self, tmp_path, monkeypatch):
        """Test --file reads from file and generates plan."""
        monkeypatch.chdir(tmp_path)

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

    def test_python_project_detected_in_needs(self, tmp_path, monkeypatch):
        """Test Python project detection appears in Environment/Needs section."""
        monkeypatch.chdir(tmp_path)

        # Create Python project indicators
        (tmp_path / "pyproject.toml").write_text("[build-system]")

        with patch("sys.argv", ["autorepro", "plan", "--desc", "tests failing"]):
            exit_code = main()

        assert exit_code == 0

        content = (tmp_path / "repro.md").read_text()

        # Should mention Python in assumptions and needs
        assert "python" in content.lower()
        assert "## Environment / Needs" in content
        assert "Python 3.7+" in content

    def test_node_project_detected_in_needs(self, tmp_path, monkeypatch):
        """Test Node.js project detection appears in Environment/Needs section."""
        monkeypatch.chdir(tmp_path)

        # Create Node.js project indicators
        (tmp_path / "package.json").write_text('{"name": "test"}')

        with patch("sys.argv", ["autorepro", "plan", "--desc", "npm test failing"]):
            exit_code = main()

        assert exit_code == 0

        content = (tmp_path / "repro.md").read_text()

        # Should mention Node in assumptions and needs
        assert "node" in content.lower()
        assert "## Environment / Needs" in content
        assert "Node.js" in content

    def test_mixed_languages_detected(self, tmp_path, monkeypatch):
        """Test multiple languages detected and mentioned."""
        monkeypatch.chdir(tmp_path)

        # Create indicators for multiple languages
        (tmp_path / "pyproject.toml").write_text("[build-system]")
        (tmp_path / "package.json").write_text('{"name": "test"}')

        with patch("sys.argv", ["autorepro", "plan", "--desc", "tests failing"]):
            exit_code = main()

        assert exit_code == 0

        content = (tmp_path / "repro.md").read_text()

        # Should mention both languages
        content_lower = content.lower()
        assert "python" in content_lower or "node" in content_lower
        assert "based on detected files" in content


class TestPlanCLIMaxCommands:
    """Test --max flag functionality."""

    def test_max_limits_command_count(self, tmp_path, monkeypatch):
        """Test --max limits the number of suggested commands."""
        monkeypatch.chdir(tmp_path)

        # Create Python project to get multiple suggestions
        (tmp_path / "pyproject.toml").write_text("[build-system]")

        with patch(
            "sys.argv",
            ["autorepro", "plan", "--desc", "pytest tox jest tests failing", "--max", "2"],
        ):
            exit_code = main()

        assert exit_code == 0

        content = (tmp_path / "repro.md").read_text()

        # Count table rows (excluding header)
        lines = content.split("\n")
        table_rows = [
            line
            for line in lines
            if line.startswith("| ")
            and "Score" not in line
            and "---" not in line
            and line.count("|") >= 3
        ]

        # Should have at most 2 command rows (excluding empty command row)
        command_rows = [
            row for row in table_rows if "`" in row
        ]  # Rows with actual commands (in backticks)
        assert len(command_rows) <= 2


class TestPlanCLIFormatFlag:
    """Test --format flag functionality."""

    def test_json_format_fallback_message(self, tmp_path, monkeypatch, capsys):
        """Test --format json prints fallback message and generates md."""
        monkeypatch.chdir(tmp_path)

        with patch("sys.argv", ["autorepro", "plan", "--desc", "test issue", "--format", "json"]):
            exit_code = main()

        assert exit_code == 0

        # Should print fallback message
        captured = capsys.readouterr()
        assert "json output not implemented yet; generating md" in captured.out

        # Should still create markdown file
        repro_file = tmp_path / "repro.md"
        assert repro_file.exists()

        content = repro_file.read_text()
        assert "# Test Issue" in content  # Should be markdown format


class TestPlanCLIIntegration:
    """Integration tests using subprocess."""

    def test_plan_help_via_subprocess(self):
        """Test plan help using subprocess."""
        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "plan", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--desc" in result.stdout
        assert "--file" in result.stdout
        assert "--force" in result.stdout
        assert "--max" in result.stdout
        assert "--format" in result.stdout

    def test_plan_missing_args_via_subprocess(self):
        """Test plan with missing arguments via subprocess."""
        result = subprocess.run(
            [sys.executable, "-m", "autorepro.cli", "plan"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "required" in (result.stdout + result.stderr).lower()

    def test_plan_success_via_subprocess(self, tmp_path):
        """Test successful plan generation via subprocess."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "autorepro.cli",
                "plan",
                "--desc",
                "pytest failing",
                "--out",
                "test_plan.md",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "test_plan.md" in result.stdout

        # Check file was created
        plan_file = tmp_path / "test_plan.md"
        assert plan_file.exists()

        content = plan_file.read_text()
        assert "# Pytest Failing" in content
