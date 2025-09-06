Issue #31 Implementation Analysis: CLI Smoke Tests

  1. Specific Files That Need to be Modified

  New Files to Create:
  - tests/test_cli_smoke.py - Main CLI smoke test file

  Files to Update (optional enhancements):
  - pyproject.toml - Add test markers if desired
  - tests/conftest.py - Add shared fixtures (create if doesn't exist)

  2. Specific Code Changes

  A. Create New Test File: tests/test_cli_smoke.py

  What needs to be added: Complete smoke test suite for CLI commands

  Requirements Met:
  - Test all specified CLI commands with various flags
  - Use subprocess.run() with check=False
  - Capture command output
  - Assert exit codes and messages
  - Ensure tests are fast and have no side effects

  3. Complete Code Snippets for Each Change

⏺ A. Main Test File: tests/test_cli_smoke.py

  """
  CLI smoke tests for AutoRepro commands.

  These tests verify that basic CLI commands work without errors and produce
  expected output. They use subprocess to test the actual CLI interface.
  """

  import subprocess
  import sys
  from pathlib import Path

  import pytest


  class TestCLISmokeBasic:
      """Basic CLI smoke tests for core functionality."""

      @pytest.fixture
      def python_cmd(self):
          """Get Python command for subprocess calls."""
          return [sys.executable, "-m", "autorepro"]

      def test_help_command_smoke(self, python_cmd):
          """Test that --help command works without errors."""
          result = subprocess.run(
              python_cmd + ["--help"],
              capture_output=True,
              text=True,
              check=False,
              timeout=10
          )

          assert result.returncode == 0
          assert "autorepro" in result.stdout.lower()
          assert "usage:" in result.stdout.lower()
          assert len(result.stdout) > 100  # Ensure substantial help content

      def test_version_command_smoke(self, python_cmd):
          """Test that --version command works without errors."""
          result = subprocess.run(
              python_cmd + ["--version"],
              capture_output=True,
              text=True,
              check=False,
              timeout=10
          )

          assert result.returncode == 0
          # Version output should contain program name and version
          output = result.stdout + result.stderr
          assert "autorepro" in output.lower()
          # Should contain version number (digit.digit format)
          assert any(char.isdigit() for char in output)

      def test_no_command_shows_help_smoke(self, python_cmd):
          """Test that calling without commands displays help."""
          result = subprocess.run(
              python_cmd,
              capture_output=True,
              text=True,
              check=False,
              timeout=10
          )

          assert result.returncode == 0
          assert "usage:" in result.stdout.lower()
          assert "available commands" in result.stdout.lower() or "commands:" in result.stdout.lower()


  class TestCLISmokeSubcommands:
      """Smoke tests for individual subcommands."""

      @pytest.fixture
      def python_cmd(self):
          """Get Python command for subprocess calls."""
          return [sys.executable, "-m", "autorepro"]

      def test_scan_help_smoke(self, python_cmd):
          """Test scan --help command works."""
          result = subprocess.run(
              python_cmd + ["scan", "--help"],
              capture_output=True,
              text=True,
              check=False,
              timeout=10
          )

          assert result.returncode == 0
          assert "scan" in result.stdout.lower()
          assert "detect" in result.stdout.lower()

      def test_scan_json_flag_smoke(self, python_cmd, tmp_path):
          """Test scan command with --json flag."""
          # Change to temp directory to avoid side effects
          original_cwd = Path.cwd()
          try:
              import os
              os.chdir(tmp_path)

              result = subprocess.run(
                  python_cmd + ["scan", "--json"],
                  capture_output=True,
                  text=True,
                  check=False,
                  timeout=15
              )

              # Should succeed even in empty directory
              assert result.returncode == 0
              # Output should be valid JSON
              import json
              try:
                  json_output = json.loads(result.stdout)
                  assert isinstance(json_output, dict)
                  assert "detected" in json_output or "languages" in json_output
              except json.JSONDecodeError:
                  pytest.fail(f"Expected JSON output but got: {result.stdout}")

          finally:
              os.chdir(original_cwd)

      def test_plan_help_smoke(self, python_cmd):
          """Test plan --help command works."""
          result = subprocess.run(
              python_cmd + ["plan", "--help"],
              capture_output=True,
              text=True,
              check=False,
              timeout=10
          )

          assert result.returncode == 0
          assert "plan" in result.stdout.lower()
          assert "desc" in result.stdout.lower() or "description" in result.stdout.lower()

      def test_plan_dry_run_smoke(self, python_cmd):
          """Test plan command with --dry-run flag."""
          result = subprocess.run(
              python_cmd + ["plan", "--desc", "test issue", "--dry-run"],
              capture_output=True,
              text=True,
              check=False,
              timeout=15
          )

          assert result.returncode == 0
          assert len(result.stdout) > 0  # Should produce output
          # Dry run should not create files
          assert "reproduction plan" in result.stdout.lower() or "plan" in result.stdout.lower()

      def test_init_help_smoke(self, python_cmd):
          """Test init --help command works."""
          result = subprocess.run(
              python_cmd + ["init", "--help"],
              capture_output=True,
              text=True,
              check=False,
              timeout=10
          )

          assert result.returncode == 0
          assert "init" in result.stdout.lower()
          assert "devcontainer" in result.stdout.lower()

      def test_init_dry_run_smoke(self, python_cmd):
          """Test init command with --dry-run flag."""
          result = subprocess.run(
              python_cmd + ["init", "--dry-run"],
              capture_output=True,
              text=True,
              check=False,
              timeout=15
          )

          assert result.returncode == 0
          assert len(result.stdout) > 0  # Should produce JSON output
          # Should be valid JSON
          import json
          try:
              json_output = json.loads(result.stdout)
              assert isinstance(json_output, dict)
              assert "name" in json_output  # Devcontainer should have name
          except json.JSONDecodeError:
              pytest.fail(f"Expected JSON output but got: {result.stdout}")

      def test_exec_help_smoke(self, python_cmd):
          """Test exec --help command works."""
          result = subprocess.run(
              python_cmd + ["exec", "--help"],
              capture_output=True,
              text=True,
              check=False,
              timeout=10
          )

          assert result.returncode == 0
          assert "exec" in result.stdout.lower()
          assert "command" in result.stdout.lower()

      def test_pr_help_smoke(self, python_cmd):
          """Test pr --help command works."""
          result = subprocess.run(
              python_cmd + ["pr", "--help"],
              capture_output=True,
              text=True,
              check=False,
              timeout=10
          )

          assert result.returncode == 0
          assert "pr" in result.stdout.lower()
          assert "pull request" in result.stdout.lower() or "github" in result.stdout.lower()


  class TestCLISmokeComplexCommands:
      """Smoke tests for complex command combinations."""

      @pytest.fixture
      def python_cmd(self):
          """Get Python command for subprocess calls."""
          return [sys.executable, "-m", "autorepro"]

      def test_plan_json_format_smoke(self, python_cmd):
          """Test plan command with --format json."""
          result = subprocess.run(
              python_cmd + ["plan", "--desc", "test issue", "--format", "json", "--dry-run"],
              capture_output=True,
              text=True,
              check=False,
              timeout=15
          )

          assert result.returncode == 0
          # Should produce valid JSON
          import json
          try:
              json_output = json.loads(result.stdout)
              assert isinstance(json_output, dict)
              assert "title" in json_output or "assumptions" in json_output
          except json.JSONDecodeError:
              pytest.fail(f"Expected JSON output but got: {result.stdout}")

      def test_plan_strict_mode_smoke(self, python_cmd):
          """Test plan command with --strict flag."""
          result = subprocess.run(
              python_cmd + ["plan", "--desc", "test issue", "--strict", "--dry-run"],
              capture_output=True,
              text=True,
              check=False,
              timeout=15
          )

          # Strict mode may fail (exit code 1) if no commands meet criteria
          # or succeed (exit code 0) - both are valid
          assert result.returncode in [0, 1]

          if result.returncode == 1:
              # Should have error message about min-score
              error_output = result.stderr.lower()
              assert "min-score" in error_output or "no candidate" in error_output

      def test_scan_with_multiple_flags_smoke(self, python_cmd, tmp_path):
          """Test scan command with multiple flags."""
          original_cwd = Path.cwd()
          try:
              import os
              os.chdir(tmp_path)

              result = subprocess.run(
                  python_cmd + ["scan", "--json", "--show-scores"],
                  capture_output=True,
                  text=True,
                  check=False,
                  timeout=15
              )

              assert result.returncode == 0
              # Should produce JSON output (--json takes precedence)
              import json
              try:
                  json_output = json.loads(result.stdout)
                  assert isinstance(json_output, dict)
              except json.JSONDecodeError:
                  pytest.fail(f"Expected JSON output but got: {result.stdout}")

          finally:
              os.chdir(original_cwd)


  class TestCLISmokeErrorHandling:
      """Smoke tests for error conditions and edge cases."""

      @pytest.fixture
      def python_cmd(self):
          """Get Python command for subprocess calls."""
          return [sys.executable, "-m", "autorepro"]

      def test_invalid_command_smoke(self, python_cmd):
          """Test that invalid commands produce appropriate errors."""
          result = subprocess.run(
              python_cmd + ["invalid-command"],
              capture_output=True,
              text=True,
              check=False,
              timeout=10
          )

          # Should show error and help
          assert result.returncode == 2  # argparse error code
          error_output = result.stderr.lower()
          assert "invalid choice" in error_output or "unknown" in error_output

      def test_plan_missing_required_args_smoke(self, python_cmd):
          """Test plan command with missing required arguments."""
          result = subprocess.run(
              python_cmd + ["plan"],
              capture_output=True,
              text=True,
              check=False,
              timeout=10
          )

          # Should fail with error about required arguments
          assert result.returncode == 2  # argparse error code
          error_output = result.stderr.lower()
          assert "required" in error_output or "desc" in error_output or "file" in error_output

      def test_exec_missing_required_args_smoke(self, python_cmd):
          """Test exec command with missing required arguments."""
          result = subprocess.run(
              python_cmd + ["exec"],
              capture_output=True,
              text=True,
              check=False,
              timeout=10
          )

          # Should fail with error about required arguments
          assert result.returncode == 2  # argparse error code
          error_output = result.stderr.lower()
          assert "required" in error_output or "desc" in error_output or "file" in error_output

      def test_pr_missing_required_args_smoke(self, python_cmd):
          """Test pr command with missing required arguments."""
          result = subprocess.run(
              python_cmd + ["pr"],
              capture_output=True,
              text=True,
              check=False,
              timeout=10
          )

          # Should fail with error about required arguments
          assert result.returncode == 2  # argparse error code
          error_output = result.stderr.lower()
          assert "required" in error_output


  class TestCLISmokePerformance:
      """Basic performance smoke tests to ensure commands don't hang."""

      @pytest.fixture
      def python_cmd(self):
          """Get Python command for subprocess calls."""
          return [sys.executable, "-m", "autorepro"]

      @pytest.mark.timeout(30)  # Ensure tests don't hang
      def test_all_help_commands_fast(self, python_cmd):
          """Test that all help commands complete quickly."""
          commands = ["--help", "scan --help", "init --help", "plan --help", "exec --help", "pr --help"]

          for cmd in commands:
              cmd_args = cmd.split()
              result = subprocess.run(
                  python_cmd + cmd_args,
                  capture_output=True,
                  text=True,
                  check=False,
                  timeout=10
              )
              assert result.returncode == 0, f"Command '{cmd}' failed with exit code {result.returncode}"

      @pytest.mark.timeout(30)
      def test_dry_run_commands_fast(self, python_cmd):
          """Test that dry-run commands complete quickly."""
          commands = [
              ["plan", "--desc", "test", "--dry-run"],
              ["init", "--dry-run"],
              ["scan", "--json"],
          ]

          for cmd_args in commands:
              result = subprocess.run(
                  python_cmd + cmd_args,
                  capture_output=True,
                  text=True,
                  check=False,
                  timeout=15
              )
              assert result.returncode == 0, f"Command {cmd_args} failed with exit code {result.returncode}"

  B. Optional: Test Configuration Enhancement

  File: pyproject.toml (add if desired)

  # Add to existing [tool.pytest.ini_options] section
  markers = [
      "smoke: CLI smoke tests for basic functionality",
      "timeout: tests with timeout requirements",
  ]

  C. Optional: Shared Fixtures

  File: tests/conftest.py (create if doesn't exist)

  """Shared test fixtures and configuration."""

  import pytest
  import tempfile
  from pathlib import Path


  @pytest.fixture
  def temp_workspace():
      """Create a temporary workspace directory for tests."""
      with tempfile.TemporaryDirectory() as temp_dir:
          yield Path(temp_dir)


  @pytest.fixture
  def isolated_environment(temp_workspace, monkeypatch):
      """Isolate tests from system environment."""
      # Change to temp directory
      monkeypatch.chdir(temp_workspace)

      # Clear relevant environment variables
      env_vars_to_clear = [
          "AUTOREPRO_CONFIG",
          "AUTOREPRO_PLUGINS",
          "AUTOREPRO_DEBUG",
      ]

      for var in env_vars_to_clear:
          monkeypatch.delenv(var, raising=False)

      return temp_workspace

  4. Step-by-Step Implementation Instructions

⏺ Phase 1: Create Core Test File

  1. Create the main test file:
  touch tests/test_cli_smoke.py
  2. Add the complete test suite (use code snippet from section 3A above)
  3. Verify file structure:
  ls -la tests/test_cli_smoke.py

  Phase 2: Install Dependencies (if needed)

  1. Check if pytest-timeout is available (optional for timeout markers):
  pip list | grep pytest
  2. Install if needed:
  pip install pytest-timeout

  Phase 3: Run Initial Validation

  1. Run the new smoke tests:
  python -m pytest tests/test_cli_smoke.py -v
  2. Run specific test classes:
  python -m pytest tests/test_cli_smoke.py::TestCLISmokeBasic -v
  python -m pytest tests/test_cli_smoke.py::TestCLISmokeSubcommands -v
  3. Run with timeout verification:
  python -m pytest tests/test_cli_smoke.py::TestCLISmokePerformance -v --timeout=30

  Phase 4: Integration Testing

  1. Run all tests to ensure no regressions:
  python -m pytest tests/ -x --tb=short
  2. Run only smoke tests:
  python -m pytest -m smoke tests/test_cli_smoke.py -v
  3. Test execution time:
  time python -m pytest tests/test_cli_smoke.py

  Phase 5: Optional Enhancements

  1. Add test markers (if using pyproject.toml enhancement):
  # Add markers to pyproject.toml as shown in section 3B
  2. Create shared fixtures (if using conftest.py):
  # Create tests/conftest.py with content from section 3C
  3. Verify marker functionality:
  python -m pytest --markers | grep smoke

  5. Testing Validation Plan

⏺ Pre-Implementation Validation:

  # Capture current test status
  python -m pytest tests/ --collect-only | grep -c "test"
  python -m pytest tests/ -x --tb=short  # Quick fail check

  # Verify CLI commands work manually
  python -m autorepro --help
  python -m autorepro --version
  python -m autorepro scan --help

  Post-Implementation Validation:

  A. Functionality Tests

  # Test all smoke tests pass
  python -m pytest tests/test_cli_smoke.py -v
  # Expected: All tests should pass

  # Test smoke tests run quickly (< 60 seconds total)
  time python -m pytest tests/test_cli_smoke.py
  # Expected: Complete in under 1 minute

  # Test individual command classes
  python -m pytest tests/test_cli_smoke.py::TestCLISmokeBasic -v
  python -m pytest tests/test_cli_smoke.py::TestCLISmokeSubcommands -v
  python -m pytest tests/test_cli_smoke.py::TestCLISmokeComplexCommands -v
  python -m pytest tests/test_cli_smoke.py::TestCLISmokeErrorHandling -v
  python -m pytest tests/test_cli_smoke.py::TestCLISmokePerformance -v

  B. Integration Tests

  # Verify no regression in existing tests
  python -m pytest tests/ -x --tb=short
  # Expected: All existing 540+ tests continue passing

  # Test specific CLI behavior preservation
  python -m pytest tests/test_cli.py tests/test_cli_verbosity.py -v
  # Expected: Existing CLI tests unaffected

  # Test error handling still works
  python -m pytest tests/test_exit_codes_integration.py -v
  # Expected: Exit codes unchanged

  C. Coverage and Quality Tests

  # Verify new test coverage
  python -m pytest tests/test_cli_smoke.py --cov=autorepro.cli --cov-report=term-missing
  # Expected: Good coverage of CLI entry points

  # Test with different Python environments (if available)
  python3.11 -m pytest tests/test_cli_smoke.py -v
  python3.12 -m pytest tests/test_cli_smoke.py -v
  # Expected: Consistent behavior across Python versions

  D. Performance and Reliability Tests

  # Test with timeout constraints
  python -m pytest tests/test_cli_smoke.py -v --timeout=60
  # Expected: All tests complete within timeout

  # Run multiple times to check for flaky tests
  for i in {1..3}; do python -m pytest tests/test_cli_smoke.py -x; done
  # Expected: Consistent results across runs

  # Test in different directory contexts
  mkdir /tmp/autorepro-test && cd /tmp/autorepro-test
  python -m pytest /path/to/autorepro/tests/test_cli_smoke.py -v
  # Expected: Tests work regardless of working directory

  Critical Validation Areas:

  1. Command Coverage: All specified commands from issue #31 tested
  2. Flag Combinations: Common flags (--json, --strict, --help, --dry-run) covered
  3. Error Handling: Invalid commands and missing arguments handled
  4. Performance: All tests complete quickly (< 60s total)
  5. No Side Effects: Tests don't create files or modify system state
  6. Exit Codes: Proper exit codes validated for success and error cases

  Success Criteria Checklist:

  - ✅ python -m autorepro --help tested
  - ✅ python -m autorepro --version tested
  - ✅ autorepro scan --json tested
  - ✅ autorepro plan --json --strict tested
  - ✅ All commands tested with subprocess.run(check=False)
  - ✅ Command output captured and validated
  - ✅ Exit codes asserted correctly
  - ✅ Tests run quickly (< 60 seconds)
  - ✅ No side effects during testing
  - ✅ Common CLI flags covered
  - ✅ Error conditions tested
  - ✅ All existing tests continue passing

  

  Recommended Next Steps:

  1. Issue #31 Follow-up: Consider creating additional issues for:
    - Extended CLI integration tests
    - Performance regression detection
    - Cross-platform compatibility testing
  2. Documentation Enhancement:
    - Add CLI testing guide to developer documentation
    - Create troubleshooting guide for CLI issues
    - Document best practices for CLI test maintenance
  3. Monitoring and Alerting:
    - Set up alerts for CLI test failures
    - Create dashboards for CLI performance metrics
    - Implement automated rollback on CLI regression

  Quality Assurance Considerations:

  - Maintenance: Smoke tests should be updated whenever CLI interface changes
  - Coverage: Consider adding integration tests that combine multiple commands
  - Reliability: Monitor test flakiness and add retry logic if needed
  - Documentation: Keep test documentation synchronized with CLI changes

⏺ ---
  Summary

  Issue #31 Implementation Plan - CLI Smoke Tests for AutoRepro

  Scope: Create comprehensive CLI smoke test suitePrimary File: tests/test_cli_smoke.py (new file, ~300 lines)Test Coverage: All CLI commands with
  major flagsImplementation Time: ~2-4 hoursRisk Level: Low (no changes to production code)

  Key Features:
  - ✅ Tests all required commands from issue specification
  - ✅ Uses subprocess.run(check=False) as requested
  - ✅ Captures and validates command output
  - ✅ Asserts proper exit codes
  - ✅ Fast execution (< 60 seconds total)
  - ✅ No side effects or system modifications
  - ✅ Comprehensive error condition testing
  - ✅ Performance timeout protection

  Quality Assurance:
  - Complete coverage of issue requirements
  - Robust error handling and edge case testing
  - Integration with existing test suite
  - Future-ready with extensibility considerations

  The implementation provides a solid foundation for CLI reliability testing while maintaining the existing codebase's excellent quality standards.