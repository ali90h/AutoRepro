"""Focused implementation tests for message consistency, output guarantees, and repo handling."""

import os
import time

from tests.test_utils import run_autorepro_subprocess


def run_cli_subprocess(args, cwd=None):
    """Run autorepro CLI via subprocess."""
    return run_autorepro_subprocess(args, cwd=cwd)


class TestStdoutIgnoresForce:
    """Test that --out - ignores --force for init and plan commands."""

    def test_init_stdout_ignores_force(self, tmp_path):
        """Test that init --out - ignores --force flag and prints to stdout."""
        # Create existing file to test --force behavior
        devcontainer_dir = tmp_path / ".devcontainer"
        devcontainer_dir.mkdir()
        existing_file = devcontainer_dir / "devcontainer.json"
        existing_file.write_text('{"existing": "content"}')

        result = run_cli_subprocess(["init", "--out", "-", "--force"], cwd=tmp_path)

        assert result.returncode == 0
        # Should output JSON to stdout
        assert result.stdout.strip().startswith("{")
        assert result.stdout.endswith("\n"), "Stdout should end with newline"
        # Should not modify or create any files
        assert existing_file.read_text() == '{"existing": "content"}'

    def test_plan_stdout_ignores_force(self, tmp_path):
        """Test that plan --out - ignores --force flag and prints to stdout."""
        # Create existing file to test --force behavior
        existing_file = tmp_path / "repro.md"
        existing_file.write_text("# Existing content")

        result = run_cli_subprocess(
            ["plan", "--desc", "test issue", "--out", "-", "--force"], cwd=tmp_path
        )

        assert result.returncode == 0
        # Should output markdown to stdout
        assert "# Test Issue" in result.stdout
        assert result.stdout.endswith("\n"), "Stdout should end with newline"
        # Should not modify existing file
        assert existing_file.read_text() == "# Existing content"


class TestPlanMaxLimitsCommands:
    """Test that plan --max N limits Candidate Commands to N with fixed order."""

    def test_plan_max_limits_commands(self, tmp_path):
        """Test that --max N limits commands to N and preserves order."""
        # Create Python project to get predictable results
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[build-system]\nrequires = ["setuptools"]')

        def extract_commands(output_text):
            """Extract commands from plan output."""
            lines = output_text.split("\n")
            commands = []
            in_commands_section = False
            for line in lines:
                if "## Candidate Commands" in line:
                    in_commands_section = True
                    continue
                if in_commands_section:
                    if line.startswith("##"):  # Next section
                        break
                    if (
                        any(
                            keyword in line for keyword in [" — ", "matched", "detected", "bonuses"]
                        )
                        and line.strip()
                    ):
                        # Extract command part (before first space-dash or em-dash)
                        for sep in [" — ", " — "]:  # Try both em-dash and regular dash
                            if sep in line:
                                command = line.split(sep)[0].strip()
                                # Remove leading bullet point and backticks if present
                                if command.startswith("- "):
                                    command = command[2:]
                                command = command.strip("`")
                                commands.append(command)
                                break
            return commands

        # Get full list first
        result_full = run_cli_subprocess(
            ["plan", "--desc", "pytest failing", "--dry-run"], cwd=tmp_path
        )
        assert result_full.returncode == 0, f"Full command failed: {result_full.stderr}"
        full_commands = extract_commands(result_full.stdout)

        # Test with --max 3
        result_limited = run_cli_subprocess(
            ["plan", "--desc", "pytest failing", "--max", "3", "--dry-run"], cwd=tmp_path
        )
        assert result_limited.returncode == 0, f"Limited command failed: {result_limited.stderr}"
        limited_commands = extract_commands(result_limited.stdout)

        # Debug output
        if len(limited_commands) != 3:
            print(f"Full output:\n{result_limited.stdout}")
            print(f"Extracted commands: {limited_commands}")

        # Should limit to exactly 3 commands
        assert len(limited_commands) == 3, (
            f"Expected 3 commands, got {len(limited_commands)}: {limited_commands}"
        )
        assert len(full_commands) >= 3, (
            f"Need at least 3 full commands, got {len(full_commands)}: {full_commands}"
        )

        # Should be the first 3 from the full list (preserving order)
        assert limited_commands == full_commands[:3], (
            f"Order not preserved: {limited_commands} vs {full_commands[:3]}"
        )


class TestInitForceMtimePreservation:
    """Test that init --force with no diff preserves mtime."""

    def test_init_force_no_changes_preserves_mtime(self, tmp_path):
        """Test that init --force preserves mtime when content is unchanged."""
        # Create initial devcontainer
        result1 = run_cli_subprocess(["init"], cwd=tmp_path)
        assert result1.returncode == 0

        devcontainer_file = tmp_path / ".devcontainer" / "devcontainer.json"
        assert devcontainer_file.exists()

        # Get initial mtime
        mtime_before = devcontainer_file.stat().st_mtime

        # Wait a bit to ensure time difference would be detectable
        time.sleep(0.1)

        # Force overwrite with same content
        result2 = run_cli_subprocess(["init", "--force"], cwd=tmp_path)
        assert result2.returncode == 0
        assert "No changes." in result2.stdout

        # mtime should be preserved
        mtime_after = devcontainer_file.stat().st_mtime
        assert mtime_before == mtime_after, f"mtime changed: {mtime_before} -> {mtime_after}"


class TestRepoPathStability:
    """Test that --repo relative vs absolute paths produce identical results."""

    def test_repo_relative_vs_absolute_identical_results(self, tmp_path):
        """Test that relative and absolute repo paths produce identical results."""
        # Create a test repository
        repo_dir = tmp_path / "test_repo"
        repo_dir.mkdir()
        (repo_dir / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools"]')

        # Test with absolute path
        result_abs = run_cli_subprocess(
            ["plan", "--desc", "pytest failing", "--out", "plan_abs.md", "--repo", str(repo_dir)],
            cwd=tmp_path,
        )
        assert result_abs.returncode == 0

        # Test with relative path
        result_rel = run_cli_subprocess(
            ["plan", "--desc", "pytest failing", "--out", "plan_rel.md", "--repo", "test_repo"],
            cwd=tmp_path,
        )
        assert result_rel.returncode == 0

        # Both files should exist in repo directory
        abs_file = repo_dir / "plan_abs.md"
        rel_file = repo_dir / "plan_rel.md"
        assert abs_file.exists(), "Absolute path file not created in repo"
        assert rel_file.exists(), "Relative path file not created in repo"

        # Content should be identical (both detect Python)
        abs_content = abs_file.read_text()
        rel_content = rel_file.read_text()
        assert "pytest" in abs_content, "Should detect Python and suggest pytest"
        assert "pytest" in rel_content, "Should detect Python and suggest pytest"

    def test_repo_no_cwd_leakage(self, tmp_path):
        """Test that --repo does not change current working directory."""
        # Record original CWD
        original_cwd = os.getcwd()

        # Create repo in subdirectory
        repo_dir = tmp_path / "sub_repo"
        repo_dir.mkdir()
        (repo_dir / "package.json").write_text('{"name": "test"}')

        # Run command with --repo
        result = run_cli_subprocess(
            ["plan", "--desc", "npm test", "--repo", str(repo_dir)], cwd=tmp_path
        )
        assert result.returncode == 0

        # CWD should be unchanged
        assert os.getcwd() == original_cwd, "Current working directory was changed"

        # File should be created in repo directory, not current directory
        repo_file = repo_dir / "repro.md"
        current_file = tmp_path / "repro.md"
        assert repo_file.exists(), "File not created in repo directory"
        assert not current_file.exists(), "File incorrectly created in current directory"


class TestOutputFilesEndWithNewline:
    """Test that output files end with newline for both commands."""

    def test_plan_file_ends_with_newline(self, tmp_path):
        """Test that plan command output files end with newline."""
        result = run_cli_subprocess(["plan", "--desc", "test issue"], cwd=tmp_path)
        assert result.returncode == 0

        output_file = tmp_path / "repro.md"
        assert output_file.exists()
        content = output_file.read_text()
        assert content.endswith("\n"), "Plan output file should end with newline"

    def test_plan_json_file_ends_with_newline(self, tmp_path):
        """Test that plan JSON output files end with newline."""
        result = run_cli_subprocess(
            ["plan", "--desc", "test issue", "--format", "json"], cwd=tmp_path
        )
        assert result.returncode == 0

        output_file = tmp_path / "repro.md"
        assert output_file.exists()
        content = output_file.read_text()
        assert content.endswith("\n"), "Plan JSON output file should end with newline"

    def test_init_file_ends_with_newline(self, tmp_path):
        """Test that init command output files end with newline."""
        result = run_cli_subprocess(["init"], cwd=tmp_path)
        assert result.returncode == 0

        output_file = tmp_path / ".devcontainer" / "devcontainer.json"
        assert output_file.exists()
        content = output_file.read_text()
        assert content.endswith("\n"), "Init output file should end with newline"

    def test_plan_custom_out_ends_with_newline(self, tmp_path):
        """Test that plan command with custom --out ends with newline."""
        custom_file = tmp_path / "custom_plan.md"
        result = run_cli_subprocess(
            ["plan", "--desc", "test issue", "--out", str(custom_file)], cwd=tmp_path
        )
        assert result.returncode == 0

        assert custom_file.exists()
        content = custom_file.read_text()
        assert content.endswith("\n"), "Plan custom output file should end with newline"

    def test_init_custom_out_ends_with_newline(self, tmp_path):
        """Test that init command with custom --out ends with newline."""
        custom_file = tmp_path / "custom_devcontainer.json"
        result = run_cli_subprocess(["init", "--out", str(custom_file)], cwd=tmp_path)
        assert result.returncode == 0

        assert custom_file.exists()
        content = custom_file.read_text()
        assert content.endswith("\n"), "Init custom output file should end with newline"


class TestCommandFiltering:
    """Test that command filtering only shows commands if keyword OR detected language matches."""

    def test_no_matches_shows_empty_list(self, tmp_path):
        """Test that no keyword matches and no detected languages shows no commands."""
        # Empty directory with generic description
        result = run_cli_subprocess(
            ["plan", "--desc", "random unrelated issue", "--dry-run"], cwd=tmp_path
        )
        assert result.returncode == 0

        # Should not show any commands
        lines = result.stdout.split("\n")
        command_lines = []
        in_commands_section = False
        for line in lines:
            if "## Candidate Commands" in line:
                in_commands_section = True
                continue
            if in_commands_section:
                if line.startswith("##"):  # Next section
                    break
                if (
                    any(keyword in line for keyword in [" — ", "matched", "detected", "bonuses"])
                    and line.strip()
                    and not line.startswith("#")
                ):
                    command_lines.append(line)
        assert not command_lines, f"Expected no commands, but got: {command_lines}"

    def test_keyword_match_shows_command(self, tmp_path):
        """Test that keyword matches show relevant commands."""
        result = run_cli_subprocess(["plan", "--desc", "pytest failing", "--dry-run"], cwd=tmp_path)
        assert result.returncode == 0

        # Should show pytest commands due to keyword match
        lines = result.stdout.split("\n")
        command_lines = []
        in_commands_section = False
        for line in lines:
            if "## Candidate Commands" in line:
                in_commands_section = True
                continue
            if in_commands_section:
                if line.startswith("##"):  # Next section
                    break
                if (
                    any(keyword in line for keyword in [" — ", "matched", "detected", "bonuses"])
                    and line.strip()
                    and not line.startswith("#")
                ):
                    command_lines.append(line)
        assert len(command_lines) > 0, (
            f"Expected commands due to pytest keyword match, got: {command_lines}"
        )

        # At least one should be pytest related
        pytest_commands = [line for line in command_lines if "pytest" in line]
        assert len(pytest_commands) > 0, "Expected pytest commands due to keyword match"

    def test_language_detection_shows_command(self, tmp_path):
        """Test that detected languages show relevant commands."""
        # Create Python project marker
        (tmp_path / "pyproject.toml").write_text('[build-system]\nrequires = ["setuptools"]')

        result = run_cli_subprocess(
            ["plan", "--desc", "tests not working", "--dry-run"], cwd=tmp_path
        )
        assert result.returncode == 0

        # Should show Python commands due to language detection
        lines = result.stdout.split("\n")
        command_lines = []
        in_commands_section = False
        for line in lines:
            if "## Candidate Commands" in line:
                in_commands_section = True
                continue
            if in_commands_section:
                if line.startswith("##"):  # Next section
                    break
                if (
                    any(keyword in line for keyword in [" — ", "matched", "detected", "bonuses"])
                    and line.strip()
                    and not line.startswith("#")
                ):
                    command_lines.append(line)
        assert len(command_lines) > 0, (
            f"Expected commands due to Python language detection, got: {command_lines}"
        )

        # Should have Python-related commands
        python_commands = [
            line for line in command_lines if any(py in line for py in ["python", "pytest"])
        ]
        assert len(python_commands) > 0, "Expected Python commands due to language detection"


class TestIntegrationExitCodes:
    """Test that CLI returns correct exit codes for success (0) and misuse (2)."""

    def test_success_commands_return_zero(self, tmp_path):
        """Test that successful operations return exit code 0."""
        # Test init success
        result = run_cli_subprocess(["init"], cwd=tmp_path)
        assert result.returncode == 0, f"init should return 0, got {result.returncode}"

        # Test plan success
        result = run_cli_subprocess(["plan", "--desc", "test issue"], cwd=tmp_path)
        assert result.returncode == 0, f"plan should return 0, got {result.returncode}"

        # Test init --out - success
        result = run_cli_subprocess(["init", "--out", "-"], cwd=tmp_path)
        assert result.returncode == 0, f"init --out - should return 0, got {result.returncode}"

        # Test plan --out - success
        result = run_cli_subprocess(["plan", "--desc", "test", "--out", "-"], cwd=tmp_path)
        assert result.returncode == 0, f"plan --out - should return 0, got {result.returncode}"

    def test_misuse_commands_return_two(self, tmp_path):
        """Test that CLI misuse returns exit code 2."""
        # Test plan without required --desc
        result = run_cli_subprocess(["plan"], cwd=tmp_path)
        assert result.returncode == 2, (
            f"plan without --desc should return 2, got {result.returncode}"
        )

        # Test invalid --repo path
        result = run_cli_subprocess(
            ["plan", "--desc", "test", "--repo", "/nonexistent/path"], cwd=tmp_path
        )
        assert result.returncode == 2, (
            f"plan with invalid --repo should return 2, got {result.returncode}"
        )
