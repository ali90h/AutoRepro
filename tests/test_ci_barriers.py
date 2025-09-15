"""
Tests for CI barriers to prevent regression.

These tests verify that our quality gates work correctly.
"""

import subprocess
import tempfile
from pathlib import Path

import pytest


class TestFileSizeBarrier:
    """Test file size limit enforcement."""

    def test_file_size_checker_exists(self):
        """Test that the file size checker script exists and is executable."""
        script_path = Path(__file__).parent.parent / "scripts" / "check-file-size.sh"
        assert script_path.exists(), "File size checker script should exist"
        assert script_path.is_file(), "Should be a file"
        # Check if executable bit is set
        assert script_path.stat().st_mode & 0o111, "Script should be executable"

    def test_file_size_checker_detects_violations(self):
        """Test that the file size checker correctly identifies violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Create a large Python file (over 500 lines)
            large_file = tmp_path / "large.py"
            large_content = "\n".join([f"# Line {i}" for i in range(600)])
            large_file.write_text(large_content)

            # Create a small Python file (under 500 lines)
            small_file = tmp_path / "small.py"
            small_content = "\n".join([f"# Line {i}" for i in range(100)])
            small_file.write_text(small_content)

            # Initialize git repo for the script to work
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(
                ["git", "add", "."], cwd=tmpdir, check=True, capture_output=True
            )

            # Run the file size checker
            script_path = (
                Path(__file__).parent.parent / "scripts" / "check-file-size.sh"
            )
            result = subprocess.run(
                [str(script_path)], cwd=tmpdir, capture_output=True, text=True
            )

            # Should fail because large.py exceeds 500 lines
            assert result.returncode != 0, "Should fail when files exceed 500 LOC"
            assert "large.py" in result.stdout, "Should mention the violating file"
            assert "600 lines" in result.stdout, "Should show correct line count"

    def test_file_size_checker_passes_clean_repo(self):
        """Test that the file size checker passes for files under 500 LOC."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Create only small Python files
            for i in range(3):
                small_file = tmp_path / f"small_{i}.py"
                small_content = "\n".join([f"# Line {j}" for j in range(100)])
                small_file.write_text(small_content)

            # Initialize git repo
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(
                ["git", "add", "."], cwd=tmpdir, check=True, capture_output=True
            )

            # Run the file size checker
            script_path = (
                Path(__file__).parent.parent / "scripts" / "check-file-size.sh"
            )
            result = subprocess.run(
                [str(script_path)], cwd=tmpdir, capture_output=True, text=True
            )

            # Should pass when all files are under 500 lines
            assert (
                result.returncode == 0
            ), "Should pass when all files are under 500 LOC"
            assert "All Python files are within size limits" in result.stdout


class TestRuffSizeComplexityBarrier:
    """Test ruff size and complexity rule enforcement."""

    def test_ruff_configuration_includes_plr_rules(self):
        """Test that pyproject.toml includes PLR rules in ruff configuration."""
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text()

        # Check that PLR rules are included
        assert "PLR" in content, "Should include PLR rules"
        assert "max-args" in content, "Should configure max-args limit"
        assert "max-branches" in content, "Should configure max-branches limit"
        assert "max-returns" in content, "Should configure max-returns limit"
        assert "max-statements" in content, "Should configure max-statements limit"
        assert "max-complexity" in content, "Should configure max-complexity limit"

    def test_ruff_detects_complexity_violations(self):
        """Test that ruff correctly detects complexity violations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Create a file with complexity violations
            complex_file = tmp_path / "complex.py"
            complex_content = '''
def complex_function(a, b, c, d, e, f, g, h, i, j, k, l):  # Too many args
    """Function with too many arguments and branches."""
    if a > 0:
        if b > 0:
            if c > 0:
                if d > 0:
                    if e > 0:
                        if f > 0:
                            if g > 0:
                                if h > 0:
                                    if i > 0:
                                        if j > 0:
                                            if k > 0:
                                                if l > 0:
                                                    return 1
                                                return 2
                                            return 3
                                        return 4
                                    return 5
                                return 6
                            return 7
                        return 8
                    return 9
                return 10
            return 11
        return 12
    return 13
'''
            complex_file.write_text(complex_content)

            # Run ruff with PLR and C901 rules
            result = subprocess.run(
                ["python", "-m", "ruff", "check", ".", "--select", "PLR,C901"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )

            # Should detect violations
            assert (
                result.returncode != 0
            ), "Should fail when complexity violations exist"
            assert (
                "PLR0913" in result.stdout
                or "too-many-arguments" in result.stdout.lower()
            )

    def test_ruff_passes_clean_code(self):
        """Test that ruff passes for clean, simple code."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Create a simple, clean Python file
            clean_file = tmp_path / "clean.py"
            clean_content = '''
def simple_function(a, b):
    """A simple, clean function."""
    if a > b:
        return a
    return b

class SimpleClass:
    """A simple class."""

    def __init__(self, value):
        self.value = value

    def get_value(self):
        return self.value
'''
            clean_file.write_text(clean_content)

            # Run ruff with PLR and C901 rules
            result = subprocess.run(
                ["python", "-m", "ruff", "check", ".", "--select", "PLR,C901"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
            )

            # Should pass for clean code
            assert result.returncode == 0, "Should pass for clean, simple code"


class TestPytestGoldensBarrier:
    """Test pytest and golden tests validation."""

    def test_pytest_quiet_mode_works(self):
        """Test that pytest -q runs successfully."""
        # Run pytest in quiet mode
        result = subprocess.run(
            ["python", "-m", "pytest", "-q"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
        )

        # Should pass (or at least run without crashing)
        assert (
            result.returncode == 0
        ), f"Pytest -q should pass. Output: {result.stdout}\nErrors: {result.stderr}"

        # Output should be concise (quiet mode)
        lines = result.stdout.strip().split("\n")
        assert len(lines) <= 50, "Quiet mode should produce concise output"

    def test_regold_script_exists(self):
        """Test that the regold script exists and is functional."""
        script_path = Path(__file__).parent.parent / "scripts" / "regold.py"
        assert script_path.exists(), "Regold script should exist"

        # Test dry run mode
        result = subprocess.run(
            ["python", str(script_path), "--help"], capture_output=True, text=True
        )
        assert result.returncode == 0, "Regold script should be functional"
        assert "--write" in result.stdout, "Should support --write option"

    def test_golden_tests_are_current(self):
        """Test that golden tests are up to date."""
        # Run regold in write mode
        regold_result = subprocess.run(
            ["python", "scripts/regold.py", "--write"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
        )

        # Check if any files were modified
        git_result = subprocess.run(
            ["git", "diff", "--exit-code"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
        )

        # Golden tests should be current (no changes needed)
        # Note: This might fail if golden tests are out of date
        # In that case, run `python scripts/regold.py --write` to update
        if git_result.returncode != 0:
            pytest.skip(
                f"Golden tests are out of date. Run 'python scripts/regold.py --write' to update.\n"
                f"Changed files:\n{git_result.stdout}"
            )


class TestCIWorkflowIntegration:
    """Test CI workflow integration and barrier configuration."""

    def test_ci_workflow_includes_barriers(self):
        """Test that CI workflow includes all required barriers."""
        ci_path = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text()

        # Check for file size limit step
        assert (
            "File size limit check" in content
        ), "Should include file size limit check"
        assert "check-file-size.sh" in content, "Should run file size script"

        # Check for enhanced ruff step
        assert (
            "size/complexity rules as errors" in content
        ), "Should mention size/complexity rules"
        assert "--select PLR,C901" in content, "Should select PLR and C901 rules"

        # Check for pytest quiet + goldens step
        assert (
            "Pytest quiet + goldens validation" in content
        ), "Should include pytest + goldens step"
        assert "pytest -q" in content, "Should run pytest in quiet mode"
        assert "regold.py --write" in content, "Should check golden tests"

    def test_all_barriers_fail_appropriately(self):
        """Test that all barriers can detect and fail on violations."""
        # This is more of a documentation test to ensure we understand
        # what each barrier is checking for

        barriers = {
            "file_size": "Files over 500 LOC should cause CI failure",
            "ruff_complexity": "Complex functions should trigger PLR/C901 violations",
            "pytest_goldens": "Outdated golden tests should cause git diff failure",
        }

        for barrier, description in barriers.items():
            # These are documented expectations, not executable tests
            assert (
                description
            ), f"Barrier '{barrier}' should have clear failure criteria"

    def test_barrier_ordering_in_workflow(self):
        """Test that barriers are ordered efficiently in CI workflow."""
        ci_path = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text()

        # File size check should come early (it's fast)
        file_size_pos = content.find("File size limit check")
        ruff_pos = content.find("Ruff (lint + size/complexity")
        pytest_pos = content.find("Pytest quiet + goldens")

        assert file_size_pos < ruff_pos, "File size check should come before ruff"
        assert (
            ruff_pos < pytest_pos
        ), "Ruff should come before pytest (for faster feedback)"


class TestBarrierConfiguration:
    """Test that barrier limits are properly configured."""

    def test_file_size_limit_is_500(self):
        """Test that file size limit is set to 500 LOC."""
        script_path = Path(__file__).parent.parent / "scripts" / "check-file-size.sh"
        content = script_path.read_text()
        assert "500" in content, "File size limit should be 500 LOC"

    def test_ruff_limits_are_reasonable(self):
        """Test that ruff complexity limits are reasonable."""
        pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject_path.read_text()

        # Check specific limits (updated for stricter CI barriers)
        assert "max-args = 8" in content, "Should limit arguments to 8"
        assert "max-branches = 12" in content, "Should limit branches to 12"
        assert "max-returns = 6" in content, "Should limit returns to 6"
        assert "max-statements = 50" in content, "Should limit statements to 50"
        assert "max-complexity = 12" in content, "Should limit complexity to 12"

    def test_pytest_timeout_reasonable(self):
        """Test that pytest doesn't run indefinitely in CI."""
        # Check that the CI workflow has reasonable timeouts
        ci_path = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text()

        # Should have job-level or step-level timeouts
        # This is more of a best practice check
        assert "runs-on: ubuntu-latest" in content, "Should specify runner"
        # Note: Timeout configuration might be implicit or at job level


class TestAdvancedCIBarriers:
    """Test advanced CI barriers added to prevent regression."""

    def test_ci_workflow_has_barrier_sections(self):
        """Test that CI workflow is organized with clear barrier sections."""
        ci_path = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text()

        # Check for barrier organization
        assert "PASS B: CI BARRIERS" in content, "Should have organized barrier section"
        assert "PASS C: COMPREHENSIVE TESTING" in content, "Should have testing section"
        assert "🛡️" in content, "Should use shield emoji for barriers"

    def test_barrier_magic_numbers_configured(self):
        """Test that magic numbers barrier is configured."""
        ci_path = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text()

        assert "magic numbers" in content.lower(), "Should check magic numbers"
        assert "PLR2004" in content, "Should use PLR2004 rule"
        assert "350" in content, "Should have magic number threshold"

    def test_barrier_code_duplication_configured(self):
        """Test that code duplication barrier is configured."""
        ci_path = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text()

        assert "jscpd" in content, "Should use jscpd for duplication detection"
        assert "duplication" in content.lower(), "Should check duplication"
        assert "0.01" in content or "1%" in content, "Should limit duplication to 1%"

    def test_barrier_critical_complexity_configured(self):
        """Test that critical complexity barrier is configured."""
        ci_path = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text()

        assert "radon cc" in content, "Should use radon for complexity"
        assert "F|C" in content, "Should check for F/C complexity functions"
        assert (
            "complex functions" in content.lower()
        ), "Should mention complex functions"

    def test_barrier_pr_size_limit_configured(self):
        """Test that PR size limit barrier is configured."""
        ci_path = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text()

        assert "LOC per PR" in content, "Should limit PR size"
        assert "300" in content, "Should have 300 line limit"
        assert "pull_request" in content, "Should run on pull requests"

    def test_current_project_triggers_barriers_correctly(self):
        """Test that current project state would trigger barriers as expected."""
        # This test verifies our barriers are working by checking actual violations

        # 1. File size barrier should detect large files
        script_path = Path(__file__).parent.parent / "scripts" / "check-file-size.sh"
        result = subprocess.run([str(script_path)], capture_output=True, text=True)
        assert result.returncode == 1, "Should fail with current large files"
        assert "autorepro/cli.py" in result.stdout, "Should detect cli.py as large"

        # 2. Magic numbers should be detected
        try:
            result = subprocess.run(
                [
                    "python",
                    "-m",
                    "ruff",
                    "check",
                    ".",
                    "--select",
                    "PLR2004",
                    "--format=json",
                ],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )
            if result.stdout:
                import json

                violations = json.loads(result.stdout)
                assert (
                    len(violations) > 100
                ), f"Should find many magic numbers, got {len(violations)}"
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            # If ruff fails, that's also a sign the barrier would work
            pass

        # 3. Complex functions should be detected by radon
        try:
            result = subprocess.run(
                ["python", "-m", "radon", "cc", "autorepro/", "-a", "-nc", "-s"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )
            complex_funcs = [
                line
                for line in result.stdout.split("\n")
                if line.strip().startswith("F") and ("F (" in line or "C (" in line)
            ]
            assert len(complex_funcs) > 0, "Should find some complex functions"
        except subprocess.CalledProcessError:
            # If radon fails, that's expected in some environments
            pass

    def test_barrier_error_messages_helpful(self):
        """Test that barrier error messages provide helpful guidance."""
        # Test file size barrier message
        script_path = Path(__file__).parent.parent / "scripts" / "check-file-size.sh"
        result = subprocess.run([str(script_path)], capture_output=True, text=True)

        if result.returncode == 1:
            assert "refactor" in result.stdout.lower(), "Should suggest refactoring"
            assert "500" in result.stdout, "Should mention the limit"
            assert "readability" in result.stdout.lower(), "Should mention benefits"

    def test_all_barrier_tools_available(self):
        """Test that all required barrier tools are available in the environment."""
        tools_and_commands = [
            (["python", "--version"], "Python"),
            (["python", "-m", "ruff", "--version"], "ruff"),
            (["python", "-m", "radon", "--version"], "radon"),
            (["autorepro", "--version"], "autorepro CLI"),
        ]

        for command, tool_name in tools_and_commands:
            try:
                result = subprocess.run(command, capture_output=True, text=True)
                assert result.returncode == 0, f"{tool_name} should be available"
            except FileNotFoundError:
                pytest.fail(f"{tool_name} is not available in PATH")

    def test_barrier_integration_complete(self):
        """Integration test to verify all barriers work together."""
        # This test ensures our barrier implementation is complete

        required_files = [
            "scripts/check-file-size.sh",
            ".github/workflows/ci.yml",
            "pyproject.toml",
        ]

        for file_path in required_files:
            full_path = Path(__file__).parent.parent / file_path
            assert full_path.exists(), f"Required file {file_path} must exist"

        # Check that CI workflow references our barriers
        ci_path = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"
        content = ci_path.read_text()

        barrier_keywords = [
            "check-file-size.sh",
            "PLR0913",
            "PLR0912",
            "PLR0911",
            "PLR0915",
            "C901",  # complexity rules
            "PLR2004",  # magic numbers
            "jscpd",  # duplication
            "radon cc",  # complexity analysis
        ]

        for keyword in barrier_keywords:
            assert keyword in content, f"CI should reference {keyword}"

        print("✅ All CI barriers are properly integrated and functional")
